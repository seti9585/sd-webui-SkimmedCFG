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
| **Single Scale** | Basic skimming. Pulls over-influenced values toward the skimming scale. | Skimming CFG (−1 = use current CFG), Full Skim Negative, Disable Flipping Filter |
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

---

## Parameters (Single Scale)

### Full Skim Negative

Forces the skimming scale to **0** on the uncond pass only, while the cond pass continues using the normal skimming scale. This maximally suppresses the uncond component in masked regions — effectively removing its outward push where it over-influences the result. Use when standard skimming still leaves burn at very high CFG.

### Disable Flipping Filter

The default mask uses three conditions (AND):

1. `sign(cond − uncond) == sign(cond)` — guidance and cond point in the same direction
2. `sign(cond) == sign(cond·cfg − uncond·(cfg−1))` — the element survives CFG amplification without sign flip
3. `sign(denoised) == sign(denoised − x_t)` — **flipping filter**: denoised is drifting outward from the noisy input

Enabling **Disable Flipping Filter** removes condition 3, widening the mask to all elements satisfying conditions 1 and 2. This applies skimming more aggressively. Try it when the default mask is too conservative.

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

Tested together with **TCFG** and **MaHiRo**. The execution order on reForge is:

```
TCFG (Pre-CFG, priority 13) → SkimmedCFG (Pre-CFG, priority 14) → CFG → MaHiRo (Post-CFG, priority 15.5)
```

No conflicts observed. When stacking multiple CFG-axis extensions, keep CFG at **7–15**; values above 20 can cause cumulative overcorrection.

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
| **Single Scale** | 基本のスキミング。過剰な値をスキミングスケールへ引き戻します。 | Skimming CFG（−1 で現在の CFG を使用）、Full Skim Negative、Disable Flipping Filter |
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

---

## パラメータ詳細（Single Scale）

### Full Skim Negative

uncond パスのスキミングスケールを強制的に **0** にします（cond パスは通常通り）。マスクが当たった領域の uncond 成分を最大限に抑制し、外側へ引っ張る力をほぼゼロにします。通常のスキミングでも高 CFG の破綻が止まらない場合に試してください。

### Disable Flipping Filter

デフォルトのマスクは以下の 3 条件の AND で決まります：

1. `sign(cond − uncond) == sign(cond)` — ガイダンスと cond が同じ方向を向いている
2. `sign(cond) == sign(cond·cfg − uncond·(cfg−1))` — CFG 増幅後も符号が反転しない（外れ値方向に安定している）
3. `sign(denoised) == sign(denoised − x_t)` — **フリッピングフィルタ**：denoised がノイズ入力から外側へ逸脱している

**Disable Flipping Filter** を有効にすると条件 3 を外し、マスクを条件 1・2 だけで決定します。補正対象が広がり、より積極的に抑制します。デフォルトのマスクが保守的すぎると感じたときに試してください。

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

**TCFG**・**MaHiRo** との同時使用を確認済みです。reForge での実行順序：

```
TCFG（Pre-CFG、priority 13）→ SkimmedCFG（Pre-CFG、priority 14）→ CFG → MaHiRo（Post-CFG、priority 15.5）
```

干渉は確認されていません。CFG 軸の拡張を複数重ねる場合は **CFG 7〜15** 以内を推奨します。20 以上では累積補正が大きくなる場合があります。

---

## 動作確認環境

- reForge（Python 3.10）— SDXL 系モデル
- Forge Neo（Python 3.12）— Anima を含む

A1111 非対応（`forge_objects` バックエンドが必要）。

---

## ライセンス

MIT License — Original algorithm © Extraltodeus (reForge adaptation: Panchovix)
