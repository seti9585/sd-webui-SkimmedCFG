> Version note: the v1/v2 sections below describe the retained legacy path. Current v3 method bounds and UI defaults are documented in [AUTO_V3_VALIDATION.md](AUTO_V3_VALIDATION.md). The transient observation schema remains v1.

# Auto observation contract v1

The transient key is `_seti_skimmedcfg_auto_v1` in runtime model_options.
The producer wrapper is independently distributed in SkimmedCFG; no sibling code is imported.
Only a live DifferenceCFG hook with `_difference_auto_token` requests observation.
Auto OFF performs no tensor observation. Each SkimmedCFG entry discards the prior record.
DifferenceCFG pops the record even outside its application interval.

Fields: version, producer function identity, monotonic producer sequence, consumer pass token,
conds_out identity, input weak reference, scalar runtime CFG and sigma, mode/settings and state.
APPLIED adds effective skimming CFG, delta tensor, output weak references and tensor mutation
versions, shape, dtype and device. Tensor weak references do not retain model outputs.
The delta tensor is retained only until the consumer pops the record or the next entry clears it.
Hook removal/re-registration clears records. A new consumer gets a new token.
The consumer requires exactly one producer immediately before itself. Earlier hooks (including
TCFG) are included in the entry prediction, not attributed to the SkimmedCFG delta.
Producer sequence and token reject replay, cross-pass and previous-generation records.

States: APPLIED, SKIPPED_GATE, SKIPPED_UNCOND, UNSUPPORTED, ERROR.
Observation exceptions do not skip the original SkimmedCFG operation. Missing/empty uncond
is safely passed through in the observation path. The original arithmetic is otherwise unchanged.
Unsupported modes still run their original SkimmedCFG behavior and expose UNSUPPORTED.

Algorithm: skim-budget-v2-experimental; v1 is retained for legacy PNGs. Budget is user-visible, persisted, from 0 to 1.
Default 0.10 is uncalibrated. Epsilon is 0.000000000001.
Norms are computed in float32 (float64 for float64 input), on the prediction device.
The direction uses the original residual expression and weights at the nominal reference.
The final candidate uses the unchanged interpolated_scales function in the original dtype.
Actual additional correction is checked against both length and alignment budgets before mutation.
Tolerance is epsilon plus 0.00001 times the length allowance; the alignment tolerance is that
quantity times the skim norm. A violation rejects the candidate without changing outputs.
Zero correction returns outputs directly, avoiding rounding at equal reference and runtime CFG.
No UNet call, candidate search or resampling is added. GPU time and memory costs remain unmeasured.
Packed statistics transfers are used, but the original hooks and scalar checks also synchronize;
this implementation does not claim a synchronization-free path.

```text
Y_0 = U_0 + s * (C_0 - U_0)
Y_1 = U_1 + s * (C_1 - U_1)
D_s = Y_1 - Y_0
k_nominal = max(0, s - k_skim)
V = -(1 - w) * (C_1 - U_1)
k_length = gamma * || D_s ||_2 / max(|| V ||_2, epsilon)
k_align = gamma * || D_s ||_2**2 / dot(D_s, V)  if dot(D_s, V) > 0
k_align = infinity                              otherwise
k = min(k_nominal, k_length, k_align)
R_auto = s - k
```

This is a correction-budget hypothesis, not an algorithm proposed or validated by the upstream author.
The paired build adds no dependency from manual DifferenceCFG to SkimmedCFG.

## v2 Linear Interpolation capability
The observation schema remains v1. Consumers advertise _difference_auto_modes.
Linear Interpolation observation requires explicit lin_interp capability. Older consumers
receive UNSUPPORTED and retain manual fallback. v2 accepts single_scale and lin_interp;
v1 accepts single_scale only. The recorded mode must match the producer's mode.
For lin_interp, effective skimming_cfg comes from lin_interp_cfg, not skimming_cfg.
The original two in-place mask updates run unchanged. The entry CFG combination is materialized
before either update; the exit is measured after both. Single Scale gates do not apply.
The original budget solver, actual-correction guard and manual functions are unchanged.

## Inference tensor mutation guards (2026-10-25)
The v1 record optionally includes a two-entry snapshots tuple. Ordinary tensors carry
their original mutation versions and None snapshots. Inference tensors carry None versions
and detached-by-clone value copies on the same device. Original tensors are never replaced.
The consumer requires the appropriate version or snapshot for each tensor; shape, dtype,
device and storage independence are validated. Snapshot equality is appended to the
existing packed statistics transfer. Mismatch is a contract rejection, never a waiver.
Both observation.py and auto_reference.py must be updated for inference tensor support.
Reason codes and observer exception stage/type/message are aggregated per request.
