"""
sd_webui_skimmed_cfg/core.py
============================
Skimmed CFG core algorithm.

Based on:
    Extraltodeus/Skimmed_CFG (original, latest)
    Panchovix/reForge-SkimmedCFG (reForge port, older)

Key fixes vs reForge built-in:
    1. Single Scale: cond pass now uses (cond_scale - 1) instead of cond_scale
    2. Linear Interpolation / Dual Scales: division-by-zero protection for CFG=1

Backend-adaptive hooking (same pattern as sd-webui-TCFG):
    * reForge / Forge Classic -> Pre-CFG  (dict args, "conds_out" style)
    * Forge Neo               -> Post-CFG (dict args, "denoised" style;
                                  Forge Neo's pre-CFG runs before model
                                  evaluation, so cond/uncond predictions are
                                  not available there)

Composition with TCFG on Forge Neo:
    TCFG and SkimmedCFG both live in Forge Neo's single
    sampler_post_cfg_function list. Forge Neo rebuilds the args dict fresh on
    every hook call with the SAME raw cond_denoised / uncond_denoised
    tensors each time, so TCFG cannot hand its damped uncond forward through
    the normal "denoised" chain. Instead TCFG (priority 13.0, runs before
    SkimmedCFG's 14.0 -- see _priority_insert_post_cfg) stashes its damped
    uncond into model_options["_tcfg_damped_uncond"]. Each mode below reads
    that key when present and falls back to the raw uncond_denoised
    otherwise, so SkimmedCFG behaves identically whether or not TCFG is
    enabled alongside it. This reproduces the reForge pipeline order
    (TCFG's pre-cfg list entry runs before SkimmedCFG's) on a backend that
    only exposes a single post-model-eval hook list.
"""

import logging

import torch

logger = logging.getLogger(__name__)

MARKER = "sd_webui_skimmed_cfg_v1"

# Mirrors SkimmedCFGScript.sorting_priority in scripts/sd_webui_skimmed_cfg.py.
# Kept in sync manually; used only to order this extension's hook within
# Forge Neo's sampler_post_cfg_function list relative to other SETI
# extensions (TCFG=13.0 runs before this, MaHiRo=15.5 runs after).
_PRIORITY = 14.0

# Qualnames of the built-in reForge SkimmedCFG closures (for detection/removal)
_BUILTIN_QUALNAMES = {
    "CFG_skimming_single_scale_pre_cfg_node.patch.<locals>.pre_cfg_patch",
    "skimReplacePreCFGNode.patch.<locals>.pre_cfg_patch",
    "SkimmedCFGLinInterpCFGPreCFGNode.patch.<locals>.pre_cfg_patch",
    "SkimmedCFGLinInterpDualScalesCFGPreCFGNode.patch.<locals>.pre_cfg_patch",
}


# ---------------------------------------------------------------------------
# Backend detection (identical logic to sd-webui-TCFG)
# ---------------------------------------------------------------------------

_BACKEND_IS_NEO = None  # cached


def _is_forge_neo_backend() -> bool:
    """
    Return True if the active backend is Forge Neo.

    Forge Neo's sampler_pre_cfg_function is called BEFORE model evaluation as
    fn(model, cond, uncond_, x, timestep, model_options) -- denoised
    predictions are not available there. On reForge / Forge Classic the hook
    receives a single dict whose "conds_out" already holds the predictions.

    Detection: Forge Neo ships backend.sampling.sampling_function with
    sampling_function_inner and calc_cond_uncond_batch; reForge / Classic use
    ldm_patched.modules.samplers instead.
    """
    global _BACKEND_IS_NEO
    if _BACKEND_IS_NEO is not None:
        return _BACKEND_IS_NEO

    is_neo = False
    try:
        from backend.sampling import sampling_function as _sf
        is_neo = (
            hasattr(_sf, "sampling_function_inner")
            and hasattr(_sf, "calc_cond_uncond_batch")
        )
    except Exception:
        is_neo = False

    _BACKEND_IS_NEO = is_neo
    logger.debug("[SkimmedCFG] backend detected: %s", "Forge Neo" if is_neo else "reForge / Forge Classic")
    return is_neo


# ---------------------------------------------------------------------------
# Priority-ordered insertion for Forge Neo's post-cfg list
# ---------------------------------------------------------------------------

def _priority_insert_post_cfg(unet, fn) -> None:
    """
    Insert fn into unet.model_options["sampler_post_cfg_function"] at the
    position that keeps SETI-suite hooks (those carrying a _sd_webui_priority
    attribute) in ascending priority order -- e.g. TCFG (13.0) before
    SkimmedCFG (14.0) before MaHiRo (15.5) -- regardless of the order in
    which their apply_*() functions happened to run this call. Third-party
    hooks without that attribute are left exactly where they already are;
    only the new fn's position relative to them is decided (inserted before
    the first tracked hook with a strictly greater priority, otherwise
    appended at the end).
    """
    key = "sampler_post_cfg_function"
    existing = unet.model_options.get(key, [])
    priority = fn._sd_webui_priority

    insert_at = len(existing)
    for i, other in enumerate(existing):
        other_priority = getattr(other, "_sd_webui_priority", None)
        if other_priority is not None and other_priority > priority:
            insert_at = i
            break

    unet.model_options[key] = existing[:insert_at] + [fn] + existing[insert_at:]


def _stashed_tcfg_uncond(args: dict):
    """Return TCFG's damped uncond from model_options if TCFG ran earlier
    in this same post-cfg call, else None."""
    model_options = args.get("model_options")
    if not isinstance(model_options, dict):
        return None
    return model_options.get("_tcfg_damped_uncond")


# ---------------------------------------------------------------------------
# Core algorithm functions
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
# Pre-CFG factories  (reForge / Forge Classic) -- UNCHANGED
# ---------------------------------------------------------------------------

def _make_single_scale_fn(skimming_cfg: float, full_skim_negative: bool, disable_flipping_filter: bool):
    """Single Scale — Pre-CFG (dict / conds_out style)."""
    @torch.no_grad()
    def _fn(args):
        conds_out  = args["conds_out"]
        cond_scale = args["cond_scale"]
        x_orig     = args["input"]

        if not torch.any(conds_out[1]):
            return conds_out

        practical_scale = cond_scale if skimming_cfg < 0 else skimming_cfg

        conds_out[1] = skimmed_CFG(
            x_orig, conds_out[1], conds_out[0],
            cond_scale,
            practical_scale if not full_skim_negative else 0,
            disable_flipping_filter,
        )
        # FIX: cond pass uses (cond_scale - 1)
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
    """Replace — Pre-CFG (dict / conds_out style)."""
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
    """Linear Interpolation — Pre-CFG (dict / conds_out style)."""
    @torch.no_grad()
    def _fn(args):
        conds_out  = args["conds_out"]
        cond_scale = args["cond_scale"]
        x_orig     = args["input"]

        if not torch.any(conds_out[1]):
            return conds_out
        if cond_scale <= 1:
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
    """Dual Scales — Pre-CFG (dict / conds_out style)."""
    @torch.no_grad()
    def _fn(args):
        conds_out  = args["conds_out"]
        cond_scale = args["cond_scale"]
        x_orig     = args["input"]

        if not torch.any(conds_out[1]):
            return conds_out
        if cond_scale <= 1:
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
# Post-CFG factories  (Forge Neo)
# ---------------------------------------------------------------------------
# Forge Neo post-CFG args dict keys:
#   "denoised"        — current CFG result (x0 estimate)
#   "cond_denoised"    — positive prediction
#   "uncond_denoised"  — negative prediction (None when CFG=1 / uncond disabled)
#   "cond_scale"       — CFG scale
#   "input"            — x_t (noisy latent)
#   "model_options"    — shared dict; read for TCFG's stashed damped uncond
#
# Each factory mirrors its Pre-CFG counterpart: damp cond/uncond the same
# way, then recompute CFG linearly:
#   denoised = uncond_skimmed + cond_scale * (cond_skimmed - uncond_skimmed)
#
# If TCFG ran earlier in this same post-cfg list, its damped uncond is used
# as the starting point instead of the raw uncond_denoised, reproducing the
# reForge pipeline order (TCFG -> SkimmedCFG). If TCFG did not run (disabled
# or not installed), behaviour is identical to before this change.
# ---------------------------------------------------------------------------

def _make_single_scale_post_fn(skimming_cfg: float, full_skim_negative: bool, disable_flipping_filter: bool):
    """Single Scale — Post-CFG (Forge Neo)."""
    @torch.no_grad()
    def _fn(args):
        uncond_denoised = args.get("uncond_denoised")
        if uncond_denoised is None or not torch.any(uncond_denoised):
            return args["denoised"]

        x_orig     = args["input"]
        cond_scale = args["cond_scale"]
        # clone to avoid mutating the tensors that downstream hooks (or the
        # TCFG stash itself) may still read
        cond   = args["cond_denoised"].clone()
        tcfg_uncond = _stashed_tcfg_uncond(args)
        uncond = (tcfg_uncond if tcfg_uncond is not None else uncond_denoised).clone()

        practical_scale = cond_scale if skimming_cfg < 0 else skimming_cfg

        uncond = skimmed_CFG(
            x_orig, uncond, cond,
            cond_scale,
            practical_scale if not full_skim_negative else 0,
            disable_flipping_filter,
        )
        cond = skimmed_CFG(
            x_orig, cond, uncond,
            cond_scale - 1,
            practical_scale,
            disable_flipping_filter,
        )
        return uncond + cond_scale * (cond - uncond)

    _fn._sd_webui_skimmed_cfg_marker = MARKER
    _fn._sd_webui_priority = _PRIORITY
    return _fn


def _make_replace_post_fn():
    """Replace — Post-CFG (Forge Neo)."""
    @torch.no_grad()
    def _fn(args):
        uncond_denoised = args.get("uncond_denoised")
        if uncond_denoised is None or not torch.any(uncond_denoised):
            return args["denoised"]

        x_orig     = args["input"]
        cond_scale = args["cond_scale"]
        cond   = args["cond_denoised"].clone()
        tcfg_uncond = _stashed_tcfg_uncond(args)
        uncond = (tcfg_uncond if tcfg_uncond is not None else uncond_denoised).clone()

        skim_mask = get_skimming_mask(x_orig, cond, uncond, cond_scale)
        uncond[skim_mask] = cond[skim_mask]

        skim_mask = get_skimming_mask(x_orig, uncond, cond, cond_scale)
        uncond[skim_mask] = cond[skim_mask]

        return uncond + cond_scale * (cond - uncond)

    _fn._sd_webui_skimmed_cfg_marker = MARKER
    _fn._sd_webui_priority = _PRIORITY
    return _fn


def _make_lin_interp_post_fn(skimming_cfg: float):
    """Linear Interpolation — Post-CFG (Forge Neo)."""
    @torch.no_grad()
    def _fn(args):
        uncond_denoised = args.get("uncond_denoised")
        if uncond_denoised is None or not torch.any(uncond_denoised):
            return args["denoised"]

        cond_scale = args["cond_scale"]
        if cond_scale <= 1:
            return args["denoised"]

        x_orig = args["input"]
        cond   = args["cond_denoised"]
        tcfg_uncond = _stashed_tcfg_uncond(args)
        uncond = (tcfg_uncond if tcfg_uncond is not None else uncond_denoised).clone()

        fallback_weight = (skimming_cfg - 1) / (cond_scale - 1)

        skim_mask = get_skimming_mask(x_orig, cond, uncond, cond_scale)
        uncond[skim_mask] = (
            cond[skim_mask] * (1 - fallback_weight)
            + uncond[skim_mask] * fallback_weight
        )

        skim_mask = get_skimming_mask(x_orig, uncond, cond, cond_scale)
        uncond[skim_mask] = (
            cond[skim_mask] * (1 - fallback_weight)
            + uncond[skim_mask] * fallback_weight
        )

        return uncond + cond_scale * (cond - uncond)

    _fn._sd_webui_skimmed_cfg_marker = MARKER
    _fn._sd_webui_priority = _PRIORITY
    return _fn


def _make_dual_scales_post_fn(skimming_cfg_positive: float, skimming_cfg_negative: float):
    """Dual Scales — Post-CFG (Forge Neo)."""
    @torch.no_grad()
    def _fn(args):
        uncond_denoised = args.get("uncond_denoised")
        if uncond_denoised is None or not torch.any(uncond_denoised):
            return args["denoised"]

        cond_scale = args["cond_scale"]
        if cond_scale <= 1:
            return args["denoised"]

        x_orig = args["input"]
        cond   = args["cond_denoised"]
        tcfg_uncond = _stashed_tcfg_uncond(args)
        uncond = (tcfg_uncond if tcfg_uncond is not None else uncond_denoised).clone()

        fallback_weight_positive = (skimming_cfg_positive - 1) / (cond_scale - 1)
        fallback_weight_negative = (skimming_cfg_negative - 1) / (cond_scale - 1)

        skim_mask = get_skimming_mask(x_orig, uncond, cond, cond_scale)
        uncond[skim_mask] = (
            cond[skim_mask] * (1 - fallback_weight_negative)
            + uncond[skim_mask] * fallback_weight_negative
        )

        skim_mask = get_skimming_mask(x_orig, cond, uncond, cond_scale)
        uncond[skim_mask] = (
            cond[skim_mask] * (1 - fallback_weight_positive)
            + uncond[skim_mask] * fallback_weight_positive
        )

        return uncond + cond_scale * (cond - uncond)

    _fn._sd_webui_skimmed_cfg_marker = MARKER
    _fn._sd_webui_priority = _PRIORITY
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
    """Remove all SkimmedCFG patches from both pre- and post-CFG lists."""
    for key in ("sampler_pre_cfg_function", "sampler_post_cfg_function"):
        existing = unet.model_options.get(key)
        if isinstance(existing, list):
            unet.model_options[key] = [fn for fn in existing if not _is_skimmed_cfg_fn(fn)]


def apply_skimmed_cfg(unet, mode: str, **kwargs):
    """
    Register SkimmedCFG on unet, choosing the correct hook for the active backend.

      * Forge Neo               -> Post-CFG, priority-ordered so it runs
                                    after TCFG (consuming its stashed damped
                                    uncond when present) and before MaHiRo.
      * reForge / Forge Classic -> Pre-CFG (original behaviour, unchanged).
    """
    remove_skimmed_cfg_patches(unet)

    # --- build the right function for the requested mode ---
    if mode == "single_scale":
        pre_fn  = _make_single_scale_fn(
            kwargs["skimming_cfg"],
            kwargs["full_skim_negative"],
            kwargs["disable_flipping_filter"],
        )
        post_fn = _make_single_scale_post_fn(
            kwargs["skimming_cfg"],
            kwargs["full_skim_negative"],
            kwargs["disable_flipping_filter"],
        )
    elif mode == "replace":
        pre_fn  = _make_replace_fn()
        post_fn = _make_replace_post_fn()
    elif mode == "lin_interp":
        pre_fn  = _make_lin_interp_fn(kwargs["skimming_cfg"])
        post_fn = _make_lin_interp_post_fn(kwargs["skimming_cfg"])
    elif mode == "dual_scales":
        pre_fn  = _make_dual_scales_fn(
            kwargs["skimming_cfg_positive"],
            kwargs["skimming_cfg_negative"],
        )
        post_fn = _make_dual_scales_post_fn(
            kwargs["skimming_cfg_positive"],
            kwargs["skimming_cfg_negative"],
        )
    else:
        raise ValueError(f"Unknown SkimmedCFG mode: {mode!r}")

    if _is_forge_neo_backend():
        _priority_insert_post_cfg(unet, post_fn)
        logger.debug("[SkimmedCFG] registered post-CFG hook (Forge Neo backend), mode=%s", mode)
    else:
        unet.set_model_sampler_pre_cfg_function(pre_fn)
        logger.debug("[SkimmedCFG] registered pre-CFG hook (reForge / Forge Classic), mode=%s", mode)

    return unet
