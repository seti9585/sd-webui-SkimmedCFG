"""
sd-webui-SkimmedCFG — Skimmed CFG for Forge-derived WebUIs
===========================================================
Location: extensions/sd-webui-SkimmedCFG/scripts/sd_webui_skimmed_cfg.py

Hook:  set_model_sampler_pre_cfg_function  (Pre-CFG)
Paper: https://github.com/Extraltodeus/Skimmed_CFG

sorting_priority: 14.0
    TCFG (13.0) → SkimmedCFG (14.0) → CFG → MaHiRo (15.5)

Fixes vs reForge built-in (Panchovix/reForge-SkimmedCFG):
    - Single Scale: cond pass uses (cond_scale - 1)  [matches original latest]
    - Lin Interp / Dual Scales: CFG=1 division-by-zero protection
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

_MODES = ["Single Scale", "Replace", "Linear Interpolation", "Dual Scales"]


def _has_forge_backend(p) -> bool:
    return hasattr(p, "sd_model") and hasattr(p.sd_model, "forge_objects")


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

            # ── Single Scale ──────────────────────────────────────────────
            with gr.Group() as grp_single:
                skimming_cfg          = gr.Slider(0.0, 10.0, value=7.0, step=0.5,
                                                  label="Skimming CFG  (−1 = use current CFG)")
                full_skim_negative    = gr.Checkbox(label="Full Skim Negative", value=False)
                disable_flip_filter   = gr.Checkbox(label="Disable Flipping Filter", value=False)

            # ── Linear Interpolation ──────────────────────────────────────
            with gr.Group(visible=False) as grp_lin:
                lin_interp_cfg = gr.Slider(0.0, 10.0, value=5.0, step=0.5,
                                           label="Skimming CFG")

            # ── Dual Scales ───────────────────────────────────────────────
            with gr.Group(visible=False) as grp_dual:
                dual_cfg_pos = gr.Slider(0.0, 10.0, value=5.0, step=0.5,
                                         label="Skimming CFG Positive")
                dual_cfg_neg = gr.Slider(0.0, 10.0, value=5.0, step=0.5,
                                         label="Skimming CFG Negative")

            # Replace has no extra params — group not needed

            def _update_visibility(m):
                return (
                    gr.Group.update(visible=(m == "Single Scale")),
                    gr.Group.update(visible=(m == "Linear Interpolation")),
                    gr.Group.update(visible=(m == "Dual Scales")),
                )

            mode.change(
                fn=_update_visibility,
                inputs=[mode],
                outputs=[grp_single, grp_lin, grp_dual],
            )

        return [enabled, mode,
                skimming_cfg, full_skim_negative, disable_flip_filter,
                lin_interp_cfg,
                dual_cfg_pos, dual_cfg_neg]

    # ------------------------------------------------------------------
    # Sampling hook
    # ------------------------------------------------------------------

    def process_before_every_sampling(self, p, *args, **kwargs):
        if len(args) >= 8:
            (self.enabled, self.mode,
             skimming_cfg, full_skim_negative, disable_flip_filter,
             lin_interp_cfg,
             dual_cfg_pos, dual_cfg_neg) = args[:8]
        else:
            logger.warning("[SkimmedCFG] process_before_every_sampling: missing args")
            return

        # XYZ Grid
        xyz = getattr(p, "_skimmed_cfg_xyz", {})
        if "enabled" in xyz:
            self.enabled = (xyz["enabled"] == "True")
        if "mode" in xyz:
            self.mode = xyz["mode"]

        if not self.enabled:
            return

        if not _has_forge_backend(p):
            logger.warning("[SkimmedCFG] Requires Forge backend.")
            return

        unet = p.sd_model.forge_objects.unet.clone()

        mode_key = {
            "Single Scale":         "single_scale",
            "Replace":              "replace",
            "Linear Interpolation": "lin_interp",
            "Dual Scales":          "dual_scales",
        }.get(self.mode, "single_scale")

        apply_skimmed_cfg(
            unet,
            mode_key,
            skimming_cfg=float(skimming_cfg),
            full_skim_negative=bool(full_skim_negative),
            disable_flipping_filter=bool(disable_flip_filter),
            lin_interp_cfg=float(lin_interp_cfg),
            skimming_cfg_positive=float(dual_cfg_pos),
            skimming_cfg_negative=float(dual_cfg_neg),
        )

        p.sd_model.forge_objects.unet = unet

        p.extra_generation_params.update({
            "skimmed_cfg": self.mode,
        })
        logger.debug("[SkimmedCFG] applied: mode=%s", self.mode)


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
