"""
sd-webui-SkimmedCFG - Skimmed CFG for Forge-derived WebUIs
===========================================================
Location: extensions/sd-webui-SkimmedCFG/scripts/sd_webui_skimmed_cfg.py

Hook:  Pre-CFG (reForge / Forge Classic) / Post-CFG (Forge Neo)
Origin: https://github.com/Extraltodeus/Skimmed_CFG

sorting_priority: 14.0
    TCFG (13.0) -> SkimmedCFG (14.0) -> CFG -> MaHiRo (15.5)

Faithful port of the current upstream node family:
    Single Scale / Replace / Linear Interpolation / Dual Scales
Single Scale additionally exposes the upstream sigma gating
(start_at / end_at / flip_at percentages).

The upstream Timed Flip / Clean Skim presets are not exposed as separate
modes: they are just Single Scale with specific parameter values (see the
README for the exact settings that reproduce each one).

The upstream Difference CFG mode is split out into its own extension
(sd-webui-DifferenceCFG); it is a mask-free, reference-scale-based global
re-adjustment and shares none of this extension's skimming machinery.
"""

import logging
import os
import sys
import traceback
from functools import partial
from typing import Any

import gradio as gr
from modules import scripts, script_callbacks

# ---------------------------------------------------------------------------
# sys.path
# ---------------------------------------------------------------------------
_EXT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _EXT_ROOT not in sys.path:
    sys.path.insert(0, _EXT_ROOT)
# ---------------------------------------------------------------------------

from sd_webui_skimmed_cfg import apply_skimmed_cfg, remove_skimmed_cfg_patches

logger = logging.getLogger(__name__)

_MODES = [
    "Single Scale",
    "Replace",
    "Linear Interpolation",
    "Dual Scales",
]

_MODE_KEY = {
    "Single Scale":         "single_scale",
    "Replace":              "replace",
    "Linear Interpolation": "lin_interp",
    "Dual Scales":          "dual_scales",
}

# PNGs generated while this extension still had the upstream "Timed Flip" /
# "Clean Skim" preset modes (removed here in favor of using Single Scale's
# own controls directly -- see README) carry "Skimmed CFG Mode: Timed Flip"
# or "Clean Skim" plus their own legacy keys. Those two values are no longer
# valid Radio choices, so the paste layer below maps them to "Single Scale"
# and reconstructs the equivalent Single Scale parameter values, keeping old
# PNGs reproducible without resurrecting the modes themselves.
_LEGACY_PRESET_MODES = {"Timed Flip", "Clean Skim"}


def _effective_mode(d: dict) -> str:
    """Resolve the Mode a pasted infotext dict should be treated as, folding
    the retired Timed Flip / Clean Skim presets into Single Scale."""
    raw = d.get("Skimmed CFG Mode", "Single Scale")
    return "Single Scale" if raw in _LEGACY_PRESET_MODES else raw


def _has_forge_backend(p) -> bool:
    return hasattr(p, "sd_model") and hasattr(p.sd_model, "forge_objects")


def _build_infotext_params(cfg: dict) -> dict:
    """Build the infotext key/value dict for the active mode.

    Keys of the four original modes are kept identical to previous versions
    so already-generated PNGs keep round-tripping. Note that
    "Skimmed CFG Scale" is intentionally shared by the Single Scale and
    Linear Interpolation modes; the read side disambiguates it by
    "Skimmed CFG Mode" (see infotext_fields in ui()). Sigma-gate keys are
    written only when they differ from the inert defaults, so PNGs made
    without gating keep their previous, shorter infotext.
    """
    mode_key = _MODE_KEY.get(cfg["mode"], "single_scale")
    params = {"Skimmed CFG Mode": cfg["mode"]}

    if mode_key == "single_scale":
        params["Skimmed CFG Scale"]         = cfg["skimming_cfg"]
        params["Skimmed CFG Use Current"]   = cfg["use_current_cfg"]
        params["Skimmed CFG Full Skim Neg"] = cfg["full_skim_negative"]
        params["Skimmed CFG Disable Flip"]  = cfg["disable_flip_filter"]
        if cfg["ss_start_at"] != 0.0:
            params["Skimmed CFG Start At"]  = cfg["ss_start_at"]
        if cfg["ss_end_at"] != 1.0:
            params["Skimmed CFG End At"]    = cfg["ss_end_at"]
        if cfg["ss_flip_at"] != 0.0:
            params["Skimmed CFG Flip At"]   = cfg["ss_flip_at"]
    elif mode_key == "lin_interp":
        params["Skimmed CFG Scale"]         = cfg["lin_interp_cfg"]
    elif mode_key == "dual_scales":
        params["Skimmed CFG Scale Pos"]     = cfg["dual_cfg_pos"]
        params["Skimmed CFG Scale Neg"]     = cfg["dual_cfg_neg"]
    # "replace" has no additional parameters
    return params


# ---------------------------------------------------------------------------
# Script
# ---------------------------------------------------------------------------

class SkimmedCFGScript(scripts.Script):

    sorting_priority = 14.0

    def __init__(self):
        self.enabled = False
        self.mode = "Single Scale"

    def title(self) -> str:
        return "Skimmed CFG"

    def show(self, is_img2img: bool):
        return scripts.AlwaysVisible

    def ui(self, is_img2img: bool):
        with gr.Accordion(open=False, label=self.title()):
            gr.HTML(
                "<p><i>"
                "<b>Pre-CFG</b>: Skims over-influenced values to a fallback CFG scale, "
                "reducing artifacts at high guidance."
                "</i></p>"
            )
            enabled = gr.Checkbox(label="Enable Skimmed CFG", value=False)
            mode    = gr.Radio(_MODES, label="Mode", value="Single Scale")

            # -- Single Scale --------------------------------------------------
            with gr.Group() as grp_single:
                skimming_cfg        = gr.Slider(0.0, 10.0, value=7.0, step=0.5,
                                                label="Skimming CFG (Single Scale)")
                use_current_cfg     = gr.Checkbox(label="Use current CFG as skimming scale",
                                                  value=False)
                full_skim_negative  = gr.Checkbox(label="Full Skim Negative", value=False)
                disable_flip_filter = gr.Checkbox(label="Disable Flipping Filter", value=False)
                ss_start_at         = gr.Slider(0.0, 1.0, value=0.0, step=0.01,
                                                label="Start At Percentage (Single Scale)")
                ss_end_at           = gr.Slider(0.0, 1.0, value=1.0, step=0.01,
                                                label="End At Percentage (Single Scale)")
                ss_flip_at          = gr.Slider(0.0, 1.0, value=0.0, step=0.01,
                                                label="Flip At Percentage (Single Scale, 0 = off)")

            # -- Linear Interpolation -------------------------------------------
            with gr.Group(visible=False) as grp_lin:
                lin_interp_cfg = gr.Slider(0.0, 10.0, value=5.0, step=0.5,
                                           label="Skimming CFG")

            # -- Dual Scales ------------------------------------------------------
            with gr.Group(visible=False) as grp_dual:
                dual_cfg_pos = gr.Slider(0.0, 10.0, value=5.0, step=0.5,
                                         label="Skimming CFG Positive")
                dual_cfg_neg = gr.Slider(0.0, 10.0, value=5.0, step=0.5,
                                         label="Skimming CFG Negative")

            # Replace has no extra params -- group not needed

            # ui-config.json persists slider value/min/max/step by label
            # string and silently overrides the code-defined values above on
            # startup. All sliders are excluded from that mechanism so a
            # future change to the value= defaults above always takes
            # effect. See the APG extension for the same pattern.
            for slider in (
                skimming_cfg, ss_start_at, ss_end_at, ss_flip_at,
                lin_interp_cfg, dual_cfg_pos, dual_cfg_neg,
            ):
                slider.do_not_save_to_config = True

            def _update_visibility(m):
                # gr.update() works on both Gradio 3.x (reForge) and 4.x (Forge Neo).
                # gr.Group.update() was removed in Gradio 4.x.
                return (
                    gr.update(visible=(m == "Single Scale")),
                    gr.update(visible=(m == "Linear Interpolation")),
                    gr.update(visible=(m == "Dual Scales")),
                )

            mode.change(
                fn=_update_visibility,
                inputs=[mode],
                outputs=[grp_single, grp_lin, grp_dual],
            )

            # Gray out the Single Scale slider while "use current CFG" is on.
            use_current_cfg.change(
                fn=lambda v: gr.update(interactive=not v),
                inputs=[use_current_cfg],
                outputs=[skimming_cfg],
            )

            # Infotext round-trip (PNG Info -> Send to txt2img / img2img).
            # Metadata is written in process() (see below). Notes on the bindings:
            #   - Enable: there is no dedicated enabled key; "Skimmed CFG Mode" is
            #     written only when active, so its presence means ON, absence OFF.
            #   - "Skimmed CFG Scale" is shared by Single Scale and Linear
            #     Interpolation, so each slider uses a Mode-gated callable: it returns
            #     None (component left untouched) unless the stored Mode is its own.
            #   - Legacy Single Scale PNGs may carry "Skimmed CFG Scale: -1" from the
            #     old sentinel UI. Those map to use_current_cfg=True and leave the
            #     slider untouched.
            #   - Unambiguous keys use plain strings; bool coercion is handled by the
            #     paste layer. Absent keys leave the component untouched, which is why
            #     Enable must be a callable (so a missing key forces OFF).
            #   - The group visibility is driven from Mode so the correct sub-panel
            #     opens on paste (mode.change does not fire on a programmatic paste);
            #     it defaults to Single Scale when Mode is absent, matching init state.
            #   - PNGs from when Timed Flip / Clean Skim still existed as modes are
            #     read via _effective_mode(): Mode resolves to "Single Scale", and
            #     use_current_cfg / full_skim_negative / disable_flip_filter /
            #     ss_flip_at are reconstructed to the fixed values those presets
            #     used to delegate to Single Scale with (see apply_skimmed_cfg's
            #     former preset block, now documented in the README instead).

            def _paste_single_scale(d):
                if _effective_mode(d) != "Single Scale":
                    return None
                if d.get("Skimmed CFG Mode") in _LEGACY_PRESET_MODES:
                    return None  # both presets pinned skimming_cfg=-1; slider stays put
                value = d.get("Skimmed CFG Scale")
                if value is None:
                    return None
                try:
                    if float(value) < 0:
                        return None  # legacy sentinel; slider stays put
                except (TypeError, ValueError):
                    return None
                return value

            def _paste_use_current(d):
                raw = d.get("Skimmed CFG Mode")
                if raw in _LEGACY_PRESET_MODES:
                    return True  # both presets pinned skimming_cfg=-1
                if raw != "Single Scale":
                    return None
                if "Skimmed CFG Use Current" in d:
                    return d["Skimmed CFG Use Current"]
                value = d.get("Skimmed CFG Scale")
                try:
                    return float(value) < 0 if value is not None else None
                except (TypeError, ValueError):
                    return None

            def _paste_full_skim_negative(d):
                raw = d.get("Skimmed CFG Mode")
                if raw in _LEGACY_PRESET_MODES:
                    return True  # both presets pinned full_skim_negative=True
                if raw != "Single Scale":
                    return None
                return d.get("Skimmed CFG Full Skim Neg")

            def _paste_disable_flip_filter(d):
                raw = d.get("Skimmed CFG Mode")
                if raw == "Clean Skim":
                    return False  # preset pinned value
                if raw == "Timed Flip":
                    return d.get("Skimmed CFG Timed Flip Reverse", False)
                if raw != "Single Scale":
                    return None
                return d.get("Skimmed CFG Disable Flip")

            def _paste_ss_flip_at(d):
                raw = d.get("Skimmed CFG Mode")
                if raw == "Clean Skim":
                    return 0.0  # preset never flips
                if raw == "Timed Flip":
                    return d.get("Skimmed CFG Timed Flip At", 0.3)
                if raw != "Single Scale":
                    return None
                return d.get("Skimmed CFG Flip At")

            self.infotext_fields = [
                (enabled, lambda d: "Skimmed CFG Mode" in d),
                (mode,    _effective_mode),

                (skimming_cfg,    _paste_single_scale),
                (use_current_cfg, _paste_use_current),
                (lin_interp_cfg,
                 lambda d: d.get("Skimmed CFG Scale") if d.get("Skimmed CFG Mode") == "Linear Interpolation" else None),

                (full_skim_negative,  _paste_full_skim_negative),
                (disable_flip_filter, _paste_disable_flip_filter),
                (ss_start_at,         "Skimmed CFG Start At"),
                (ss_end_at,           "Skimmed CFG End At"),
                (ss_flip_at,          _paste_ss_flip_at),

                (dual_cfg_pos,        "Skimmed CFG Scale Pos"),
                (dual_cfg_neg,        "Skimmed CFG Scale Neg"),

                (grp_single, lambda d: gr.update(visible=(_effective_mode(d) == "Single Scale"))),
                (grp_lin,    lambda d: gr.update(visible=(d.get("Skimmed CFG Mode") == "Linear Interpolation"))),
                (grp_dual,   lambda d: gr.update(visible=(d.get("Skimmed CFG Mode") == "Dual Scales"))),
            ]

            return [enabled, mode,
                    skimming_cfg, use_current_cfg, full_skim_negative, disable_flip_filter,
                    ss_start_at, ss_end_at, ss_flip_at,
                    lin_interp_cfg,
                    dual_cfg_pos, dual_cfg_neg]

    # ------------------------------------------------------------------
    # Effective configuration (UI args + XYZ Grid override)
    # ------------------------------------------------------------------

    def _resolve(self, p, args):
        if len(args) < 12:
            return None
        (enabled, mode,
         skimming_cfg, use_current_cfg, full_skim_negative, disable_flip_filter,
         ss_start_at, ss_end_at, ss_flip_at,
         lin_interp_cfg,
         dual_cfg_pos, dual_cfg_neg) = args[:12]

        xyz = getattr(p, "_skimmed_cfg_xyz", {})
        if "enabled" in xyz:
            enabled = (xyz["enabled"] == "True")
        if "mode" in xyz:
            mode = xyz["mode"]

        return {
            "enabled":             bool(enabled),
            "mode":                mode,
            "skimming_cfg":        float(skimming_cfg),
            "use_current_cfg":     bool(use_current_cfg),
            "full_skim_negative":  bool(full_skim_negative),
            "disable_flip_filter": bool(disable_flip_filter),
            "ss_start_at":         float(ss_start_at),
            "ss_end_at":           float(ss_end_at),
            "ss_flip_at":          float(ss_flip_at),
            "lin_interp_cfg":      float(lin_interp_cfg),
            "dual_cfg_pos":        float(dual_cfg_pos),
            "dual_cfg_neg":        float(dual_cfg_neg),
        }

    # ------------------------------------------------------------------
    # Metadata write (runs once before sampling so create_infotext captures it)
    # ------------------------------------------------------------------

    def process(self, p, *args):
        cfg = self._resolve(p, args)
        if cfg is None or not cfg["enabled"]:
            return
        p.extra_generation_params.update(_build_infotext_params(cfg))

    # ------------------------------------------------------------------
    # Hook application (correct timing for forge_objects.unet)
    # ------------------------------------------------------------------

    def process_before_every_sampling(self, p, *args, **kwargs):
        cfg = self._resolve(p, args)
        if cfg is None:
            logger.warning("[SkimmedCFG] process_before_every_sampling: missing args")
            return

        self.enabled = cfg["enabled"]
        self.mode = cfg["mode"]

        if not cfg["enabled"]:
            return

        if not _has_forge_backend(p):
            logger.warning("[SkimmedCFG] Requires Forge backend.")
            return

        unet = p.sd_model.forge_objects.unet.clone()

        mode_key = _MODE_KEY.get(cfg["mode"], "single_scale")

        # Fold the "use current CFG" checkbox into the -1 sentinel expected
        # by core.py (core.py itself is sentinel-based, matching upstream).
        effective_skimming_cfg = -1.0 if cfg["use_current_cfg"] else cfg["skimming_cfg"]

        apply_skimmed_cfg(
            unet,
            mode_key,
            skimming_cfg=effective_skimming_cfg,
            full_skim_negative=cfg["full_skim_negative"],
            disable_flipping_filter=cfg["disable_flip_filter"],
            start_at_percentage=cfg["ss_start_at"],
            end_at_percentage=cfg["ss_end_at"],
            flip_at_percentage=cfg["ss_flip_at"],
            lin_interp_cfg=cfg["lin_interp_cfg"],
            skimming_cfg_positive=cfg["dual_cfg_pos"],
            skimming_cfg_negative=cfg["dual_cfg_neg"],
        )

        p.sd_model.forge_objects.unet = unet
        logger.debug("[SkimmedCFG] applied: mode=%s", cfg["mode"])


# ---------------------------------------------------------------------------
# XYZ Grid
# ---------------------------------------------------------------------------

def _set_xyz(p, x: Any, xs: Any, *, field: str) -> None:
    if not hasattr(p, "_skimmed_cfg_xyz"):
        p._skimmed_cfg_xyz = {}
    p._skimmed_cfg_xyz[field] = x


def _register_xyz() -> None:
    xyz_grid = None
    for script in scripts.scripts_data:
        if script.script_class.__module__ == "xyz_grid.py":
            xyz_grid = script.module
            break
    if xyz_grid is None:
        return

    new_axes = [
        xyz_grid.AxisOption(
            "(Skimmed CFG) Enabled",
            str,
            partial(_set_xyz, field="enabled"),
            choices=lambda: ["True", "False"],
        ),
        xyz_grid.AxisOption(
            "(Skimmed CFG) Mode",
            str,
            partial(_set_xyz, field="mode"),
            choices=lambda: _MODES,
        ),
    ]

    if not any(x.label.startswith("(Skimmed CFG)") for x in xyz_grid.axis_options):
        xyz_grid.axis_options.extend(new_axes)


def _on_before_ui() -> None:
    try:
        _register_xyz()
    except Exception:
        print(f"[sd-webui-SkimmedCFG] XYZ Grid error:\n{traceback.format_exc()}")


script_callbacks.on_before_ui(_on_before_ui)
