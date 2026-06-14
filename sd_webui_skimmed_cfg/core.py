"""
sd_webui_skimmed_cfg/core.py
============================
Skimmed CFG core algorithm.

Based on the latest original by Extraltodeus:
    https://github.com/Extraltodeus/Skimmed_CFG

Key fixes vs reForge built-in:
    1. Single Scale: cond pass now uses (cond_scale - 1) instead of cond_scale
    2. Linear Interpolation / Dual Scales: division-by-zero protection for CFG=1
"""

import torch

MARKER = "sd_webui_skimmed_cfg_v1"

# Qualnames of the built-in reForge SkimmedCFG closures (for detection/removal)
_BUILTIN_QUALNAMES = {
    "CFG_skimming_single_scale_pre_cfg_node.patch.<locals>.pre_cfg_patch",
    "skimReplacePreCFGNode.patch.<locals>.pre_cfg_patch",
    "SkimmedCFGLinInterpCFGPreCFGNode.patch.<locals>.pre_cfg_patch",
    "SkimmedCFGLinInterpDualScalesCFGPreCFGNode.patch.<locals>.pre_cfg_patch",
}


# ---------------------------------------------------------------------------
# Core functions (identical to original)
# ---------------------------------------------------------------------------

@torch.no_grad()
def get_skimming_mask(
    x_orig, cond, uncond, cond_scale,
    return_denoised=False, disable_flipping_filter=False
):
    denoised = x_orig - (
        (x_orig - uncond) + cond_scale * ((x_orig - cond) - (x_orig - uncond))
    )
    matching_pred_signs = (cond - uncond).sign() == cond.sign()
    matching_diff_after = (
        cond.sign() == (cond * cond_scale - uncond * (cond_scale - 1)).sign()
    )
    if disable_flipping_filter:
        outer_influence = matching_pred_signs & matching_diff_after
    else:
        deviation_influence = denoised.sign() == (denoised - x_orig).sign()
        outer_influence = matching_pred_signs & matching_diff_after & deviation_influence
    if return_denoised:
        return outer_influence, denoised
    else:
        return outer_influence


@torch.no_grad()
def skimmed_CFG(
    x_orig, cond, uncond, cond_scale, skimming_scale, disable_flipping_filter=False
):
    outer_influence, denoised = get_skimming_mask(
        x_orig, cond, uncond, cond_scale, True, disable_flipping_filter
    )
    low_cfg_denoised_outer = x_orig - (
        (x_orig - uncond) + skimming_scale * ((x_orig - cond) - (x_orig - uncond))
    )
    low_cfg_denoised_outer_difference = denoised - low_cfg_denoised_outer
    cond[outer_influence] = cond[outer_influence] - (
        low_cfg_denoised_outer_difference[outer_influence] / cond_scale
    )
    return cond


# ---------------------------------------------------------------------------
# Pre-CFG function factories (one per mode)
# ---------------------------------------------------------------------------

def _make_single_scale_fn(skimming_cfg: float, full_skim_negative: bool, disable_flipping_filter: bool):
    """
    Single Scale mode.
    FIX vs reForge built-in: cond pass uses (cond_scale - 1), matching original latest.
    """
    @torch.no_grad()
    def _fn(args):
        conds_out  = args["conds_out"]
        cond_scale = args["cond_scale"]
        x_orig     = args["input"]

        if not torch.any(conds_out[1]):
            return conds_out

        practical_scale = cond_scale if skimming_cfg < 0 else skimming_cfg

        # uncond pass
        conds_out[1] = skimmed_CFG(
            x_orig, conds_out[1], conds_out[0],
            cond_scale,
            practical_scale if not full_skim_negative else 0,
            disable_flipping_filter,
        )
        # cond pass — FIX: use (cond_scale - 1)
        conds_out[0] = skimmed_CFG(
            x_orig, conds_out[0], conds_out[1],
            cond_scale - 1,
            practical_scale,
            disable_flipping_filter,
        )
        return conds_out

    _fn._sd_webui_skimmed_cfg_marker = MARKER
    return _fn


def _make_replace_fn():
    """Replace mode: uncond is replaced by cond in skimmed regions."""
    @torch.no_grad()
    def _fn(args):
        conds_out  = args["conds_out"]
        cond_scale = args["cond_scale"]
        x_orig     = args["input"]

        if not torch.any(conds_out[1]):
            return conds_out

        cond   = conds_out[0]
        uncond = conds_out[1]

        skim_mask = get_skimming_mask(x_orig, cond, uncond, cond_scale)
        uncond[skim_mask] = cond[skim_mask]

        skim_mask = get_skimming_mask(x_orig, uncond, cond, cond_scale)
        uncond[skim_mask] = cond[skim_mask]

        return [cond, uncond]

    _fn._sd_webui_skimmed_cfg_marker = MARKER
    return _fn


def _make_lin_interp_fn(skimming_cfg: float):
    """
    Linear Interpolation mode.
    FIX vs reForge built-in: division-by-zero protection when CFG=1.
    """
    @torch.no_grad()
    def _fn(args):
        conds_out  = args["conds_out"]
        cond_scale = args["cond_scale"]
        x_orig     = args["input"]

        if not torch.any(conds_out[1]):
            return conds_out
        if cond_scale <= 1:  # FIX: prevent division by zero
            return conds_out

        fallback_weight = (skimming_cfg - 1) / (cond_scale - 1)

        skim_mask = get_skimming_mask(x_orig, conds_out[0], conds_out[1], cond_scale)
        conds_out[1][skim_mask] = (
            conds_out[0][skim_mask] * (1 - fallback_weight)
            + conds_out[1][skim_mask] * fallback_weight
        )

        skim_mask = get_skimming_mask(x_orig, conds_out[1], conds_out[0], cond_scale)
        conds_out[1][skim_mask] = (
            conds_out[0][skim_mask] * (1 - fallback_weight)
            + conds_out[1][skim_mask] * fallback_weight
        )

        return conds_out

    _fn._sd_webui_skimmed_cfg_marker = MARKER
    return _fn


def _make_dual_scales_fn(skimming_cfg_positive: float, skimming_cfg_negative: float):
    """
    Dual Scales mode.
    FIX vs reForge built-in: division-by-zero protection when CFG=1.
    """
    @torch.no_grad()
    def _fn(args):
        conds_out  = args["conds_out"]
        cond_scale = args["cond_scale"]
        x_orig     = args["input"]

        if not torch.any(conds_out[1]):
            return conds_out
        if cond_scale <= 1:  # FIX: prevent division by zero
            return conds_out

        fallback_weight_positive = (skimming_cfg_positive - 1) / (cond_scale - 1)
        fallback_weight_negative = (skimming_cfg_negative - 1) / (cond_scale - 1)

        skim_mask = get_skimming_mask(x_orig, conds_out[1], conds_out[0], cond_scale)
        conds_out[1][skim_mask] = (
            conds_out[0][skim_mask] * (1 - fallback_weight_negative)
            + conds_out[1][skim_mask] * fallback_weight_negative
        )

        skim_mask = get_skimming_mask(x_orig, conds_out[0], conds_out[1], cond_scale)
        conds_out[1][skim_mask] = (
            conds_out[0][skim_mask] * (1 - fallback_weight_positive)
            + conds_out[1][skim_mask] * fallback_weight_positive
        )

        return conds_out

    _fn._sd_webui_skimmed_cfg_marker = MARKER
    return _fn


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------

def _is_skimmed_cfg_fn(fn) -> bool:
    if getattr(fn, "_sd_webui_skimmed_cfg_marker", None) == MARKER:
        return True
    qualname = getattr(fn, "__qualname__", "")
    if qualname in _BUILTIN_QUALNAMES:
        return True
    return False


def remove_skimmed_cfg_patches(unet) -> None:
    """Remove all SkimmedCFG pre_cfg_function patches from unet."""
    key = "sampler_pre_cfg_function"
    existing = unet.model_options.get(key, [])
    if isinstance(existing, list):
        unet.model_options[key] = [fn for fn in existing if not _is_skimmed_cfg_fn(fn)]


def apply_skimmed_cfg(unet, mode: str, **kwargs):
    """Apply SkimmedCFG pre_cfg_function (removes any existing first)."""
    remove_skimmed_cfg_patches(unet)

    if mode == "single_scale":
        fn = _make_single_scale_fn(
            kwargs["skimming_cfg"],
            kwargs["full_skim_negative"],
            kwargs["disable_flipping_filter"],
        )
    elif mode == "replace":
        fn = _make_replace_fn()
    elif mode == "lin_interp":
        fn = _make_lin_interp_fn(kwargs["skimming_cfg"])
    elif mode == "dual_scales":
        fn = _make_dual_scales_fn(
            kwargs["skimming_cfg_positive"],
            kwargs["skimming_cfg_negative"],
        )
    else:
        raise ValueError(f"Unknown SkimmedCFG mode: {mode!r}")

    unet.set_model_sampler_pre_cfg_function(fn)
    return unet
