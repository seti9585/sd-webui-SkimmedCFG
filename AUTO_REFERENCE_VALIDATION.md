> Historical record / 履歴資料：当時の実装・検証状況です。最新状況は [2026-11-17の検証記録](VALIDATION_2026-11-17.md) を参照してください。

# Auto Reference CFG v2 検証記録 — 2026-10-24

## 結論

実装・CPU試験済みの実験版です。画質・速度の合格版ではありません。
設計書は参考資料として使用し、実画像のGate 0/1を通過したとは扱わず、
未校正の試作実装を別途作成しました。公開採用のGate 3/4も未達です。

## 固定した元コード

- DifferenceCFG: `7627e44abf66fc5aa89168514bec88b6065a477a`
- SkimmedCFG: `f142d31e784e7fa97b6cdbd2019ff400fb66e0a2`
- 初回改修時はgit statusで差分なしを確認。v2は初回改修ZIPと全ファイル一致を確認しSHA256を保存してから着手。
- reForge本体のリビジョン・実行コードは、許可されたextensionsの範囲外のため未確認。
- GitHubの閲覧取得は失敗したため、最新mainとの一致を主張せずローカルの上記版を基準に使用。

## CPU試験

Python 3.13 / PyTorch 2.14.1+cpu。WebUI環境とは別の専用テスト環境。
`tests/test_auto_reference.py` と元コードの検証用コピーを同梱。

- 手動4方式 × SkimmedCFG有無 × 4数値形式 × 4seed = 128条件で元コードと完全一致。
- 観測のみ48条件でSkimmedCFGの元出力と完全一致。uncondとcondを更新した後の差分を検証。
- Auto 120条件: 67条件で適用、13条件で実補正量の予算超過等を安全側に拒否、40条件で追加補正ゼロ。
- 古い記録、再利用、違うCFG/sigma/入力、順序、pass切替、途中のテンソル変更を拒否。
- ゼロ・定数・非有限値・極大値、負例なし、空テンソル、適用区間外を試験。
- 旧SkimmedCFG・他モード・他Methodの手動フォールバック、Neoの非対応表示を試験。
- PNG設定の書き出しと復元関数を代用WebUIで試験。旧PNGはAuto OFF。
- 元の手動計算関数と補正式は変更なし。追加のUNet推論を呼ぶコードはなし。

テストログは同梱の `AUTO_REFERENCE_TEST_LOG.txt` を参照。
CPU試験の完全一致をGPU画像の完全一致と読み替えないでください。

## 未実施

実機のhook順序・モデルclone、固定seed画像比較、PNG Infoの実画面操作、
Illustriousでの係数校正、画質の目視評価、5回以上のWarm速度・VRAM測定、
実機UNet呼び出し回数計測、Hires.fix・LoRA・他拡張との同時運用。
追加推論なしはコード構造の確認であり、実機計測結果ではありません。
NumPy未導入の警告がテスト環境で出ますが、本試験はNumPyを使いません。

## 再試験方法

通常利用には追加インストールもテスト実行も不要です。開発用の再試験だけ行う場合：

- 必要ライブラリ：`python -m pip install torch --index-url https://download.pytorch.org/whl/cpu`
- 2拡張を同じ親フォルダに置き、DifferenceCFGフォルダで実行：`python -X utf8 -B -m unittest discover -s tests -p "test_*.py" -v`

## 変更点

DifferenceCFGにAuto UI・予算・アルゴリズム保存復元・状態集計を追加。
SkimmedCFGに必要時だけ観測する処理を追加し、補正式と既存UI値は維持。
両拡張の無効化時に、自分の古いhookと観測情報を除去する処理を追加。
LICENSEを保持し、NOTICEに今回の変更を追記。

## Linear Interpolation優先対応の検証
- 前版のSingle Scale実験版を基準とし、元のLinear Interpolation補正式は変更なし。
- CFG 20 / Linear Interpolation 3、手動4方式・4数値形式・8seedの128条件が元コードと完全一致。
- 観測のみ32条件で元の2段階の出力と差分を照合。
- 同設定の4数値形式・12seed・予算0.10/0.25/0.50の144条件でAUTO_APPLIED。実補正量が長さ・方向の両上限以内。
- テスト全28項目PASS。Single Scaleの旧試験とv1互換を含む。
- v1画像復元時のLinear Interpolationは従来の手動フォールバックを維持。
- 実画像の画質・GPU速度・実機のPNG往復は未検証。
