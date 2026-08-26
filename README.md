# sd-webui-SkimmedCFG

**EN** | [日本語](#日本語)

Pre-CFG guidance extension for Stable Diffusion WebUI (Forge-based).  
"Skims" over-influenced prediction values down to a lower fallback scale, suppressing burn and over-saturation at high CFG.

Original algorithm by **Extraltodeus** — [Skimmed_CFG](https://github.com/Extraltodeus/Skimmed_CFG)  
reForge port by **Panchovix** — [reForge-SkimmedCFG](https://github.com/Panchovix/reForge-SkimmedCFG)
> reForge previously included Skimmed CFG as a built-in, but it has since been separated into Panchovix's standalone repository. Install this extension if you want Skimmed CFG on reForge.

---

## Installation

**Extensions → Install from URL:**

```
https://github.com/seti9585/sd-webui-SkimmedCFG
```

---

## Modes

| Mode | Description | Parameters |
| ---- | ----------- | ---------- |
| **Single Scale** | Basic skimming. Pulls over-influenced values toward the skimming scale. | Skimming CFG, Use current CFG, Full Skim Negative, Disable Flipping Filter, Start / End / Flip At |
| **Replace** | Replaces uncond values with cond values in skimmed regions (effective scale 1 there). | — |
| **Linear Interpolation** | Interpolates between values instead of replacing. Recommended by the original author. | Skimming CFG |
| **Dual Scales** | Two independent scales for cond and uncond passes. | Skimming CFG Positive / Negative |

---

## Skimming CFG

The skimming scale is, in the original author's words, "how much do you like them burned."

| Skimming CFG | Effect |
| ------------ | ------ |
| 2 – 3 | Maximum anti-burn |
| 4     | Cruise scale |
| 5 – 7 | Colorful / strong style |

Side effects: better prompt adherence, sharper images, fewer positive/negative conflicts.  
Very low scales with too few steps can occasionally fuse details.


### There is no neutral setting

**Skimmed CFG has no value of Skimming CFG at which it becomes a no-op.** This was checked directly: on a fixed seed with the skimming scale swept across its range, no setting reproduced the disabled output bitwise, and none came close. The skimming mask is built from sign agreement between the predictions, so it selects elements to rewrite regardless of what scale those elements are then pulled toward. Setting Skimming CFG equal to the session CFG does not disable the effect; it only changes the target.

To measure what this extension does to an image, **untick Enable Skimmed CFG**. Do not try to neutralise it with parameter values.

This is worth stating because the sibling extension `sd-webui-DifferenceCFG`, which comes from the same upstream repository, *does* have an exact no-op point. Do not carry that assumption across.

### The default of 7.0 is not a safe midpoint

The default Skimming CFG of 7.0 sits at the steepest part of the response curve. Measured on a fixed seed, the interval between 6.5 and 7.0 produced the largest change per unit of any part of the range, so small adjustments near the default move the image more than the same adjustment made anywhere else.

The scale is also designed for the upstream operating range of roughly **CFG 6 to 32 and above**. At a session CFG of 7 the whole axis is compressed and the useful travel is short. If you work at low CFG, expect the slider to feel abrupt, and prefer changes of 0.5 or smaller near the default.

---

## Parameters (Single Scale)

### Skimming CFG / Use current CFG

**Skimming CFG** is the fallback scale over-influenced values are pulled toward. Enabling **Use current CFG as skimming scale** makes the fallback track the session CFG instead of a fixed value; the Skimming CFG slider is greyed out while it is on. (Internally this is the upstream `-1` sentinel — the slider is just a friendlier way to expose it.)

### Full Skim Negative

Forces the skimming scale to **0** on the uncond pass only, while the cond pass continues using the normal skimming scale. This maximally suppresses the uncond component in masked regions — effectively removing its outward push where it over-influences the result. Use when standard skimming still leaves burn at very high CFG.

### Disable Flipping Filter

The default mask uses three conditions (AND):

1. `sign(cond − uncond) == sign(cond)` — guidance and cond point in the same direction
2. `sign(cond) == sign(cond·cfg − uncond·(cfg−1))` — the element survives CFG amplification without sign flip
3. `sign(denoised) == sign(denoised − x_t)` — **flipping filter**: denoised is drifting outward from the noisy input

Enabling **Disable Flipping Filter** removes condition 3, widening the mask to all elements satisfying conditions 1 and 2. This applies skimming more aggressively. Try it when the default mask is too conservative.

### Start At / End At Percentage

Sigma gating that limits skimming to a slice of the sampling schedule, expressed as denoising progress (0 = first step, 1 = last step). Skimming is active only while progress is between **Start At** and **End At**. The defaults (Start 0.0 / End 1.0) cover the whole schedule, so skimming runs on every step unless you narrow the window.

### Flip At Percentage

When set above 0, the flipping filter (condition 3 above) is **inverted** for steps *before* this progress point, then behaves normally afterward. This lets the early, composition-defining steps use the opposite masking behaviour from the later, detail steps. Left at the default 0.0, the filter never flips and this control does nothing.

---

## Why Timed Flip / Clean Skim are not separate modes

The current upstream has two extra nodes — **Timed Flip** (`SkimFlipPreCFG`) and **Clean Skim** (`ConstantSkimPreCFG`) — that this extension does **not** expose as separate modes. That is a deliberate choice, not a missing feature: both are simply Single Scale with fixed parameter values, and Single Scale's own controls above already reproduce them exactly.

ComfyUI's node-graph paradigm benefits from a dedicated node per preset — a node is the natural unit there. A single WebUI panel that already surfaces every underlying parameter gains nothing from duplicating the same behaviour as extra radio choices; it would only lengthen the mode list. So the presets are documented here as Single Scale settings instead of shipped as modes.

To reproduce each one:

| Single Scale control | Clean Skim | Timed Flip |
| -------------------- | ---------- | ---------- |
| Use current CFG | ON | ON |
| Full Skim Negative | ON | ON |
| Disable Flipping Filter | OFF | *(the "reverse" value)* |
| Flip At Percentage | 0.0 (default) | your flip point (upstream default 0.3) |
| Start / End At | 0.0 / 1.0 (default) | 0.0 / 1.0 (default) |

**Compatibility note:** PNGs generated while these still existed as modes (`Skimmed CFG Mode: Timed Flip` / `Clean Skim`) still paste correctly — the infotext reader maps them to Single Scale and restores the equivalent settings automatically. You do not need to reconfigure anything by hand.

---

## Parameters (Dual Scales)

Dual Scales assigns separate skimming scales to the cond and uncond passes:

- **uncond pass** uses **Skimming CFG Negative**
- **cond pass** uses **Skimming CFG Positive**

**Skimming CFG Positive** controls how strongly over-influenced *cond* values are pulled back. Lowering it suppresses the prompt-driven component, making the result less saturated and more subdued.

**Skimming CFG Negative** controls how strongly over-influenced *uncond* values are pulled back. Lowering it reduces the outward push from the negative prompt, softening its influence in masked regions.

Typical use: keep Positive near the CFG scale to preserve prompt adherence; lower Negative to suppress burn caused by the uncond component without affecting positive guidance.

---

## Differences from the reForge built-in

1. **Single Scale** — the cond pass uses `(cond_scale − 1)`, matching Extraltodeus' latest original.
2. **Linear Interpolation / Dual Scales** — division-by-zero protection at CFG = 1.
3. **Forge Neo** — backend-adaptive: registers as Post-CFG on Forge Neo (Pre-CFG predictions are not available there), Pre-CFG on reForge / Forge Classic.

---

## Note on flow-matching DiT models

Skimmed CFG is designed around **UNet epsilon-space predictions** (SDXL and similar).  
On flow-matching DiT models such as **Anima**, the model outputs velocity fields rather than noise predictions, so the sign-comparison logic in `get_skimming_mask` operates under different assumptions. The extension runs without errors, but the anti-burn effect may differ from UNet behaviour.

---

## Algorithm

```
# Pre-CFG: edits cond / uncond before CFG combines them

mask = sign(cond − uncond) == sign(cond)
     & sign(cond) == sign(cond·cfg − uncond·(cfg − 1))
     & sign(denoised) == sign(denoised − x)     # flipping filter (optional)

low        = cfg(x, cond, uncond, skimming_scale)
denoised   = cfg(x, cond, uncond, cfg_scale)
cond[mask] −= (denoised − low)[mask] / cfg_scale
```

Only "over-influenced" values — those that blow out at high CFG — are pulled back toward the skimming scale; all others retain the full CFG.

In practice (verified on reForge + SDXL, CFG 30, 35 steps), roughly **40–44 % of elements** are masked per step. The norm change per step is small (Δ ≈ −0.02 to −0.10) because only masked elements are touched, but the cumulative effect is sufficient to recover usable quality from otherwise broken high-CFG images.

---

## Compatibility with other extensions

The execution order across the suite on reForge is:

```
TCFG (13.0) → SkimmedCFG (14.0) → DifferenceCFG (14.2) → APG (14.5) → CFG
  → CFGZeroStar (15.0) → FreSca (15.2) → MaHiRo (15.5) → CFGNorm (16.0) → CFGRegulator (16.5)
```

No conflicts observed. When stacking multiple CFG-axis extensions, keep CFG at **7–15**; values above 20 can cause cumulative overcorrection.

Note that both this extension and DifferenceCFG rewrite the unconditional prediction, and DifferenceCFG runs immediately after. The interaction of two such rewrites in the same chain has not been measured; if results look over-corrected, disable one at a time to isolate the cause before adjusting values.

### Chain ordering and the debug dump

Forge-derived backends append pre-CFG hooks in registration order, which is effectively alphabetical and shifts with whatever else is installed. This extension inserts itself at priority 14.0 instead. Note that this is separate from `sorting_priority`, which controls only the accordion's position in the UI.

Set `SD_WEBUI_SETI_DEBUG=1` before launching to have the assembled chain printed at sampling time:

```
[SkimmedCFG] pre-CFG chain: _tcfg_pre_cfg_fn(13.0) -> _skimmedcfg_pre_cfg_fn(14.0)
```

If a hook you expected is missing, that extension is not enabled or failed to register. If the order differs from the list above, something in the chain is not participating in priority insertion.

---

## Tested environments

- reForge (Python 3.10) — SDXL-family models
- Forge Neo (Python 3.12) — including Anima

Not compatible with A1111 (`forge_objects` backend required).

---
---

# 日本語

**[English](#sd-webui-skimmedcfg)** | 日本語

Forge 系 WebUI 向け Pre-CFG ガイダンス拡張機能。  
過剰に影響した予測値を低いフォールバックスケールへ「すくい取る（skim）」ことで、高 CFG での焼き付き・過飽和を抑えます。

原アルゴリズム：**Extraltodeus** — [Skimmed_CFG](https://github.com/Extraltodeus/Skimmed_CFG)  
reForge 移植：**Panchovix** — [reForge-SkimmedCFG](https://github.com/Panchovix/reForge-SkimmedCFG)
> reForge にはかつて Skimmed CFG が組み込まれていましたが、現在は分離され Panchovix 氏のリポジトリとして独立しています。reForge で使用する場合は本拡張機能をインストールしてください。

---

## インストール

**Extensions → Install from URL:**

```
https://github.com/seti9585/sd-webui-SkimmedCFG
```

---

## モード

| モード | 説明 | パラメータ |
| ---- | --- | ------ |
| **Single Scale** | 基本のスキミング。過剰な値をスキミングスケールへ引き戻します。 | Skimming CFG、Use current CFG、Full Skim Negative、Disable Flipping Filter、Start / End / Flip At |
| **Replace** | スキム対象領域で uncond を cond に置き換えます（その領域は実効スケール 1）。 | — |
| **Linear Interpolation** | 置き換えではなく値を線形補間します。原作者の推奨モード。 | Skimming CFG |
| **Dual Scales** | cond パスと uncond パスに個別のスケールを指定できます。 | Skimming CFG Positive / Negative |

---

## Skimming CFG（スキミングスケール）

スキミングスケールは、原作者いわく「どれくらい焼けたのが好きか」を表す値です。

| Skimming CFG | 効果 |
| ------------ | --- |
| 2〜3 | アンチバーン最大 |
| 4    | 巡航スケール |
| 5〜7 | 鮮やか・強いスタイル |

副作用：プロンプト追従の向上、よりシャープな画像、ポジ／ネガの衝突の減少。  
スケールが低すぎてステップ数も少ない場合、ディテールが稀に融合することがあります。


### 無効化される設定は存在しない

**Skimmed CFG には、Skimming CFG をどの値にしても効果が無効化される点がありません。** これは実測で確認しています。固定シードでスキミングスケールを全域にわたって走査しましたが、無効時の出力をビット単位で再現する設定は存在せず、近づく設定もありませんでした。スキミングマスクは予測同士の符号一致から構築されるため、書き換える要素の選別は、その要素をどのスケールへ引き寄せるかとは無関係に行われます。Skimming CFG をセッション CFG と等しくしても効果は消えず、引き寄せ先が変わるだけです。

本拡張機能が画像に何をしているかを測るには、**Enable Skimmed CFG のチェックを外してください。** パラメータ値で無効化しようとしないでください。

これを明記するのは、同じ上流リポジトリ由来の姉妹拡張 `sd-webui-DifferenceCFG` には厳密な無効化点が*存在する*ためです。一方の前提を他方へ引き継がないでください。

### 既定値 7.0 は安全な中間点ではない

Skimming CFG の既定値 7.0 は、応答曲線の最も急峻な部分に位置しています。固定シードでの実測では、6.5 から 7.0 の区間が全域で単位あたりの変化量が最大でした。既定値付近での小さな調整は、同じ幅の調整を他のどこで行うよりも画像を大きく動かします。

またこのスケールは、上流が想定する **CFG 6 から 32 以上**の運用域に向けて設計されています。セッション CFG 7 では軸全体が圧縮され、実用的な可動域が短くなります。低い CFG で使う場合、スライダは急峻に感じられるはずです。既定値付近では 0.5 以下の刻みで調整することをお勧めします。

---

## パラメータ詳細（Single Scale）

### Skimming CFG / Use current CFG

**Skimming CFG** は、過剰な値を引き戻す先となるフォールバックスケールです。**Use current CFG as skimming scale** を有効にすると、固定値ではなくセッション CFG に追従したフォールバックになります（有効中は Skimming CFG スライダーがグレーアウトします）。内部的には原典の `-1` センチネルに相当しますが、スライダーはそれを分かりやすく露出したものです。

### Full Skim Negative

uncond パスのスキミングスケールを強制的に **0** にします（cond パスは通常通り）。マスクが当たった領域の uncond 成分を最大限に抑制し、外側へ引っ張る力をほぼゼロにします。通常のスキミングでも高 CFG の破綻が止まらない場合に試してください。

### Disable Flipping Filter

デフォルトのマスクは以下の 3 条件の AND で決まります：

1. `sign(cond − uncond) == sign(cond)` — ガイダンスと cond が同じ方向を向いている
2. `sign(cond) == sign(cond·cfg − uncond·(cfg−1))` — CFG 増幅後も符号が反転しない（外れ値方向に安定している）
3. `sign(denoised) == sign(denoised − x_t)` — **フリッピングフィルタ**：denoised がノイズ入力から外側へ逸脱している

**Disable Flipping Filter** を有効にすると条件 3 を外し、マスクを条件 1・2 だけで決定します。補正対象が広がり、より積極的に抑制します。デフォルトのマスクが保守的すぎると感じたときに試してください。

### Start At / End At Percentage

スキミングをサンプリングスケジュールの一部区間だけに限定する σ ゲートです。デノイズ進行度（0 = 最初のステップ、1 = 最後のステップ）で指定し、進行度が **Start At** と **End At** の間にあるステップでのみスキミングが有効になります。デフォルト（Start 0.0 / End 1.0）は全区間をカバーするため、窓を狭めない限り毎ステップ動作します。

### Flip At Percentage

0 より大きい値を設定すると、この進行度**より前**のステップだけフリッピングフィルタ（上記の条件 3）が**反転**し、それ以降は通常動作に戻ります。構図が決まる序盤のステップと、ディテールを詰める終盤のステップとで、マスクの挙動を逆にできます。デフォルトの 0.0 のままではフィルタは反転せず、このコントロールは何もしません。

---

## Timed Flip / Clean Skim を独立モードにしていない理由

原典の現行版には **Timed Flip**（`SkimFlipPreCFG`）と **Clean Skim**（`ConstantSkimPreCFG`）という追加ノードがありますが、本拡張ではこれらを独立モードとして**用意していません**。これは機能の欠落ではなく、意図的な判断です。どちらも実体は「特定のパラメータ値に固定した Single Scale」にすぎず、上記の Single Scale のコントロールだけで完全に同じ挙動を再現できるためです。

ComfyUI のノードグラフでは「1 プリセット = 1 ノード」に意味があります（ノードが自然な単位だからです）。一方、すべての基礎パラメータを既に露出している WebUI の単一パネルでは、同じ挙動を別のラジオ選択肢として複製しても得るものがなく、モード一覧が長くなるだけです。そこで本拡張では、これらを独立モードとして持たせるのではなく、Single Scale の設定として下記に記載する形にしています。

各プリセットの再現方法：

| Single Scale のコントロール | Clean Skim | Timed Flip |
| --------------------------- | ---------- | ---------- |
| Use current CFG | ON | ON |
| Full Skim Negative | ON | ON |
| Disable Flipping Filter | OFF | *（「反転」させたい値）* |
| Flip At Percentage | 0.0（既定） | 任意のフリップ地点（原典の既定は 0.3） |
| Start / End At | 0.0 / 1.0（既定） | 0.0 / 1.0（既定） |

**互換性について：** これらがモードとして存在していた頃に生成した PNG（`Skimmed CFG Mode: Timed Flip` / `Clean Skim`）も、正しくペーストできます。infotext リーダーが自動的に Single Scale へ変換し、同等の設定を復元するため、手作業で設定し直す必要はありません。

---

## パラメータ詳細（Dual Scales）

Dual Scales では cond パスと uncond パスに別々のスキミングスケールを指定します：

- **uncond パス** → **Skimming CFG Negative** を使用
- **cond パス** → **Skimming CFG Positive** を使用

**Skimming CFG Positive** は、過剰な *cond* 値をどこまで引き戻すかを決めます。下げるとプロンプト駆動の成分が抑えられ、全体が落ち着いた印象になります。

**Skimming CFG Negative** は、過剰な *uncond* 値をどこまで引き戻すかを決めます。下げるとネガティブプロンプトの押し返し力が和らぎ、マスク領域での過剰な影響を抑えます。

典型的な使い方：Positive は CFG scale に近い値を保ってプロンプト追従を維持しつつ、Negative を下げて uncond 起因の破綻だけを抑える。

---

## reForge 組み込みとの差異

1. **Single Scale** — cond パスで `(cond_scale − 1)` を使用し、Extraltodeus の最新オリジナルに合わせています。
2. **Linear Interpolation / Dual Scales** — CFG = 1 でのゼロ除算を防止。
3. **Forge Neo 対応** — バックエンド自動判別：Forge Neo では Post-CFG、reForge / Forge Classic では Pre-CFG として動作します（Forge Neo の Pre-CFG はモデル評価前に呼ばれるため予測値が存在しないため）。

---

## フローマッチング系 DiT モデルについて

Skimmed CFG は **UNet の epsilon 空間予測**（SDXL 等）を前提に設計されています。  
**Anima** などのフローマッチング系 DiT モデルでは、モデルが出力するのはノイズ予測ではなく速度場であるため、`get_skimming_mask` の符号比較ロジックが異なる空間で動作します。エラーなく動作しますが、アンチバーン効果は UNet 系とは異なる挙動になる場合があります。

---

## アルゴリズム

```
# Pre-CFG：CFG が合成する前に cond / uncond を編集

mask = sign(cond − uncond) == sign(cond)
     & sign(cond) == sign(cond·cfg − uncond·(cfg − 1))
     & sign(denoised) == sign(denoised − x)     # フリッピングフィルタ（任意）

low        = cfg(x, cond, uncond, skimming_scale)
denoised   = cfg(x, cond, uncond, cfg_scale)
cond[mask] −= (denoised − low)[mask] / cfg_scale
```

高 CFG で破綻する「過剰に影響した値」だけをスキミングスケールへ引き戻し、それ以外はフル CFG を維持します。

実測値（reForge + SDXL、CFG 30、35 ステップ）では、**1 ステップあたり約 40〜44 % の要素**にマスクが当たります。ステップごとのノルム変化は小さい（Δ ≈ −0.02〜−0.10）ですが、これはマスクが当たった要素だけを局所的に修正する設計によるものです。累積効果として、通常では破綻する高 CFG 画像を実用品質に回復させることを確認しています。

---

## 他拡張との併用

reForge でのスイート全体の実行順序：

```
TCFG (13.0) → SkimmedCFG (14.0) → DifferenceCFG (14.2) → APG (14.5) → CFG
  → CFGZeroStar (15.0) → FreSca (15.2) → MaHiRo (15.5) → CFGNorm (16.0) → CFGRegulator (16.5)
```

干渉は確認されていません。CFG 軸の拡張を複数重ねる場合は **CFG 7〜15** 以内を推奨します。20 以上では累積補正が大きくなる場合があります。

なお本拡張機能と DifferenceCFG はいずれも無条件予測を書き換えており、DifferenceCFG は直後に実行されます。同一チェーン内で 2 つの書き換えが相互作用した場合の挙動は未測定です。過補正に見える場合は、値を調整する前に 1 つずつ無効化して原因を切り分けてください。

### チェーン順序とデバッグダンプ

Forge 系バックエンドは pre-CFG フックを登録順に追加します。これは実質的にアルファベット順であり、他に何がインストールされているかによって変動します。本拡張機能は代わりに優先度 14.0 の位置へ自身を挿入します。これは `sorting_priority` とは別物である点に注意してください。`sorting_priority` は UI 上のアコーディオンの位置のみを制御します。

起動前に `SD_WEBUI_SETI_DEBUG=1` を設定すると、サンプリング時に組み立てられたチェーンが出力されます。

```
[SkimmedCFG] pre-CFG chain: _tcfg_pre_cfg_fn(13.0) -> _skimmedcfg_pre_cfg_fn(14.0)
```

想定していたフックが現れない場合、その拡張機能が有効化されていないか、登録に失敗しています。順序が上記の一覧と異なる場合、チェーン内のいずれかが優先度挿入に参加していません。

---

## 動作確認環境

- reForge（Python 3.10）— SDXL 系モデル
- Forge Neo（Python 3.12）— Anima を含む

A1111 非対応（`forge_objects` バックエンドが必要）。

---

## Acknowledgements / 謝辞

**Extraltodeus**

The Skimmed CFG algorithm is the work of [**Extraltodeus**](https://github.com/Extraltodeus), published in [Skimmed_CFG](https://github.com/Extraltodeus/Skimmed_CFG). This extension exists only because that work exists.

Skimmed CFG のアルゴリズムは [**Extraltodeus**](https://github.com/Extraltodeus) 氏によるもので、[Skimmed_CFG](https://github.com/Extraltodeus/Skimmed_CFG) として公開されています。本拡張機能は同氏の成果があってはじめて成立しています。

**Shiba-2-shiba**

Development of this whole extension suite started from the articles and Forge Classic implementation of [**Shiba-2-shiba**](https://note.com/gentle_murre488). Sincere thanks.

本拡張スイート全体の開発は、[**Shiba-2-shiba**](https://note.com/gentle_murre488) 氏の記事および Forge Classic 向け実装をきっかけに始まりました。深く感謝します。

---

## License / ライセンス

**Apache License 2.0** — see [LICENSE](LICENSE) and [NOTICE](NOTICE).

Copyright (c) 2026 seti9585

This extension is a port of the Skimmed CFG algorithm from [Extraltodeus/Skimmed_CFG](https://github.com/Extraltodeus/Skimmed_CFG), which is licensed under the Apache License 2.0. `get_skimming_mask()`, `skimmed_CFG()` and all four mode bodies are ported without algorithmic change, so this is a derivative work and is distributed under the same licence. The modifications made in porting it are recorded in `NOTICE` as the licence requires.

Earlier revisions of this file stated MIT and named Panchovix's reForge adaptation alongside the original. Both were wrong. Apache-2.0 code cannot be redistributed under MIT, and the licence additionally requires the licence text and a change notice to travel with the derivative; neither file was present. Panchovix's `reForge-SkimmedCFG` carries no licence file of its own and is not the source this port follows. This has been corrected.

本拡張機能は [Extraltodeus/Skimmed_CFG](https://github.com/Extraltodeus/Skimmed_CFG) の Skimmed CFG アルゴリズムを移植したものです。同リポジトリは Apache License 2.0 でライセンスされています。`get_skimming_mask()`、`skimmed_CFG()` および 4 モードの本体はすべてアルゴリズムを変更せずに移植しているため、本拡張機能は派生物であり、同一ライセンスで配布します。移植にあたって加えた変更は、ライセンスの要求に従い `NOTICE` に記録しています。

本ファイルの以前の版は MIT を表示し、原作者と並べて Panchovix 氏の reForge 向け改変を挙げていました。いずれも誤りです。Apache-2.0 のコードを MIT で再配布することはできず、さらに同ライセンスはライセンス本文と変更告知が派生物とともに配布されることを要求しますが、どちらのファイルも存在しませんでした。また Panchovix 氏の `reForge-SkimmedCFG` にはライセンスファイルが存在せず、本移植が追随している出典でもありません。以上により訂正しました。
