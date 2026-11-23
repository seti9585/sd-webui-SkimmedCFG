"""Transient, opt-in observations for DifferenceCFG; no cross-package imports."""

import weakref

import torch

KEY = "_seti_skimmedcfg_auto_v1"


def observe_hook(original, mode, settings, gates):
    """Measure the existing hook without changing its two-pass arithmetic."""
    sequence = 0

    @torch.no_grad()
    def observed(args):
        nonlocal sequence
        options = args.get("model_options", {})
        options.pop(KEY, None)
        consumers = [fn for fn in options.get("sampler_pre_cfg_function", [])
                     if getattr(fn, "_difference_auto_token", None) is not None]
        if not consumers:
            return original(args)
        sequence += 1
        observed._auto_sequence = sequence
        record = {"version": 1, "sequence": sequence, "producer": observed,
                  "token": consumers[0]._difference_auto_token,
                  "state": "ERROR", "mode": mode, "settings": dict(settings)}
        before = None
        phase = "entry_metadata"
        try:
            outputs = args["conds_out"]
            c, u = outputs
            scale = float(args["cond_scale"])
            sigma = args["sigma"]
            sigma_value = float(sigma.reshape(-1)[0]) if torch.is_tensor(sigma) else float(sigma)
            record.update(outputs_id=id(outputs), scale=scale, sigma_value=sigma_value,
                          input_ref=weakref.ref(args["input"]))
            if u is None or u.numel() == 0:
                record["state"] = "SKIPPED_UNCOND"
                options[KEY] = record
                return outputs
            supported = mode == "single_scale" or (
                mode == "lin_interp" and
                "lin_interp" in getattr(consumers[0], "_difference_auto_modes", ())
            )
            if not supported or scale <= 1 or options.get("sampler_cfg_function"):
                record["state"] = "UNSUPPORTED"
            elif u is None or not torch.any(u):
                record["state"] = "SKIPPED_UNCOND"
            elif mode == "single_scale" and (sigma_value <= gates[1] or sigma_value >= gates[0]):
                record["state"] = "SKIPPED_GATE"
            elif c.shape != u.shape or c.ndim != 4 or c.numel() == 0:
                record["state"] = "UNSUPPORTED"
            else:
                if mode == "lin_interp":
                    record["skimming_cfg"] = float(settings["lin_interp_cfg"])
                else:
                    record["skimming_cfg"] = scale if settings["skimming_cfg"] < 0 else float(settings["skimming_cfg"])
                phase = "entry_prediction"
                dtype = torch.float64 if c.dtype == torch.float64 else torch.float32
                before = u.to(dtype) + scale * (c.to(dtype) - u.to(dtype))
        except Exception as exc:
            record.update(error=type(exc).__name__, error_stage=phase,
                          error_message=str(exc).replace("\n", " ")[:240])
        # Observation errors must never suppress the original correction.
        result = original(args)
        try:
            if before is not None:
                phase = "exit_prediction"
                c, u = result
                after = u.to(before.dtype) + scale * (c.to(before.dtype) - u.to(before.dtype))
                phase = "mutation_guard"
                # Inference tensors have no version counter. Preserve their
                # exact values for a device-side integrity check by the consumer.
                inference = (torch.is_inference(c), torch.is_inference(u))
                versions = tuple(None if flag else tensor._version
                                 for tensor, flag in zip((c, u), inference))
                snapshots = tuple(tensor.clone() if flag else None
                                  for tensor, flag in zip((c, u), inference))
                record.update(state="APPLIED", delta=after - before,
                              cond_ref=weakref.ref(c), uncond_ref=weakref.ref(u),
                              versions=versions, snapshots=snapshots, shape=tuple(c.shape),
                              dtype=c.dtype, device=c.device)
        except Exception as exc:
            record.update(state="ERROR", error=type(exc).__name__, error_stage=phase,
                          error_message=str(exc).replace("\n", " ")[:240])
        options[KEY] = record
        return result

    observed.__name__ = original.__name__
    observed.__dict__.update(original.__dict__)
    observed._skim_auto_version = 1
    observed._skim_auto_mode = mode
    observed._auto_sequence = 0
    return observed
