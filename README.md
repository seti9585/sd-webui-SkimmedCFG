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
| **Dual Scales** | Two independent scales — higher *Positive* leans toward saturation; *Negative* the opposite. | Skimming CFG Positive / Negative |

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

low       = cfg(x, cond, uncond, skimming_scale)
denoised  = cfg(x, cond, uncond, cfg_scale)
cond[mask] −= (denoised − low)[mask] / cfg_scale
```

Only "over-influenced" values — those that blow out at high CFG — are pulled back toward the skimming scale; all others retain the full CFG.

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
| **Dual Scales** | 2 つの独立したスケール。*Positive* を上げると高彩度方向、*Negative* は逆方向。 | Skimming CFG Positive / Negative |

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

low       = cfg(x, cond, uncond, skimming_scale)
denoised  = cfg(x, cond, uncond, cfg_scale)
cond[mask] −= (denoised − low)[mask] / cfg_scale
```

高 CFG で破綻する「過剰に影響した値」だけをスキミングスケールへ引き戻し、それ以外はフル CFG を維持します。

---

## 動作確認環境

- reForge（Python 3.10）— SDXL 系モデル
- Forge Neo（Python 3.12）— Anima を含む

A1111 非対応（`forge_objects` バックエンドが必要）。

---

## ライセンス

MIT License — Original algorithm © Extraltodeus (reForge adaptation: Panchovix)
