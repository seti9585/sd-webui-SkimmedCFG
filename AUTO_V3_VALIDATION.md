# Auto v3 / 全4方式へのAuto対応 — 2026-11-17

## English

New UI sessions use skim-budget-v3-experimental. All four DifferenceCFG methods support Auto on the reForge Pre-CFG path with SkimmedCFG Linear Interpolation or Single Scale. Manual math and the observation schema are unchanged. Neo retains manual fallback.

Squared and root distance use their respective weighting curves in both the budget direction and the actual native-method candidate. Absolute sum uses a conservative L1 Lipschitz bound to select a reference within the same length and alignment budgets. It does not assume that its L1 ratio is monotonic in Reference CFG. The resulting candidate is the original absolute_sum formula at the recorded reference, not a blend with an unrelated method. Low-precision candidates that exceed either budget are rejected unchanged.

The original linear_distance v2 arithmetic remains unchanged. v1 and v2 identifiers retain their previous behavior: the other three methods still fall back to manual. Restoring an old PNG retains its algorithm identifier. To test v3 after installation, fully restart WebUI and use a fresh UI page; do not restore old v2 metadata as the starting settings. Confirm DiffCFG Auto Algorithm is skim-budget-v3-experimental in the resulting generation information.

Budget 0 performs no additional correction. Session CFG is adjustable, including 30; synthetic tests cover CFG 7, 20 and 30. Earlier v2 image results are not v3 image validation. New methods remain experimental pending user-run images. Hires.fix, Neo Auto and broad extension compatibility remain unverified. No GPU performance or VRAM benchmark was performed.

See [regression output](AUTO_V3_TEST_LOG.txt). The full suite has 63 tests: the previous 57 and six new tests. The new matrix exercises four methods, two SkimmedCFG modes, four dtypes, three CFG values, four Budgets and four seeds: 1536 cases per execution path, 4608 across ordinary CPU, inference CPU and inference CUDA. Applied outputs are checked against both budget inequalities and the original native method at the recorded reference. Budget-zero outputs and rejected candidates must preserve the input. Additional tests cover degenerate inputs, v1/v2 fallbacks and v3/v2 linear equivalence.

An initial regression failure came from passing a v3 identifier to the archived v2 factory in a defect-reproduction test. That test now explicitly selects v2; its original failure/success assertions remain intact.

## 日本語

**変更内容：** 新規UIのAutoをv3とし、DifferenceCFGの全4方式へ対応しました。SkimmedCFG側の対応は従来どおりLinear InterpolationとSingle Scaleです。手動の補正式と観測情報の形式は変更していません。Neoでは引き続き手動へ戻ります。

squared_distanceとroot_distanceは、方式ごとの重みをBudget計算と実際の補正の双方に使用します。absolute_sumはReferenceに対する変化が常に単調とは限らないため、L1ノルムの変化の上限を利用して保守的にReferenceを選びます。全方式で実際の出力を再検査し、長さ・方向のBudget上限を超えた場合は追加補正を見送ります。低精度の丸めで見送る場合もあります。

**互換性：** v1・v2のPNGは以前の動作を維持します。残る3方式をAutoで使うにはv3が必要です。WebUIを完全に再起動して新しく開いた画面から設定し、生成情報のDiffCFG Auto Algorithmがskim-budget-v3-experimentalになっていることを確認してください。旧PNGを読み込むと旧アルゴリズムも復元されます。

**検証：** 既存57件と追加6件の合計63テストを実施。追加の合成入力行列はCPU通常・CPU推論・CUDA推論で合計4608条件です。適用時のBudget上限と記録Referenceでの元方式との一致、Budget 0と拒否時の出力維持、旧版互換性を確認します。最終結果は[実行ログ](AUTO_V3_TEST_LOG.txt)を参照してください。

**未確認：** v3の実画像・画質、速度・VRAM増分、Hires.fix、広範な他拡張との併用です。CFG 30も合成入力では検証対象ですが、実画像での確認とは区別します。以前のv2画像比較は[別記録](VALIDATION_2026-11-17.md)です。

## Absolute sum bound

The following bound concerns exact arithmetic. The final native-dtype guard is authoritative for applied outputs.

```text
d = C - U
f(r) = || U + r * d ||_1
L = s * || d ||_1 / f(s)
| s * f(r) / f(s) - s | <= L * | r - s |
V_bound = -L * d
k_length = gamma * || D_s ||_2 / || V_bound ||_2
k_align = gamma * || D_s ||_2**2 / | dot(D_s, V_bound) |
R_auto = s - min(max(0, s - k_skim), k_length, k_align)
```

Zero denominators, non-finite values and numerical violations are handled by the existing no-correction/invalid paths. No candidate search or additional model evaluation is used. Absolute-sum-specific reductions run on the prediction device and reuse the existing statistics transfers.