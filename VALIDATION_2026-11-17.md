# Validation / 検証記録 — 2026-11-17

## Scope

57 existing regression tests passed with no skips in the installed reForge virtual environment. These are synthetic/reference tests, not GPU image-quality or performance measurements. Both extensions are exercised by the DifferenceCFG suite; SkimmedCFG has no separate tests directory in this installation.

User-run WebUI generation results and user-confirmed UI restoration are recorded below. Images were viewed as chat attachments; outputs directories were not scanned or read. No pixel-level comparison or new image generation was performed by the documentation task.

## 確認条件

利用者提示のPNG生成情報：amanatsuIllustrious_v11（0842c2a1d8）、sdxl.vae.safetensors、896×1152、Euler a / Karras、35ステップ、CFG 20、Clip skip 2、ENSD 31337。SkimmedCFGはLinear Interpolation 3、DifferenceCFGはEnd At 0.8、Auto時はlinear_distance / Budget 0.03。reForgeの生成情報は739b2e1dを示した。SageAttentionの使用は引き継ぎ資料の環境情報であり、提示生成ログだけから再確認したものではない。

## 実画像・操作の結果

| 検証 | 根拠と結果 |
|---|---|
| seed 2667135954 | AUTO_APPLIED=22、Reference平均17.734357072、floor_hits=0 |
| seed 2667135955 | AUTO_APPLIED=22、Reference平均17.733498349、floor_hits=0 |
| seed 2667135956 | AUTO_APPLIED=22、Reference平均17.724472419、floor_hits=0 |
| 共通 | DIFF_GATE_OFF=13。上記Autoの提示ログに契約エラー・手動への切り替えなし |
| Budget 0 | AUTO_NO_CORRECTION=22。00003とDifferenceCFG無効の00001が目視一致 |
| Auto ONのPNG復元 | 利用者確認：OFF / Budget 0.05からON / 0.03へ復元 |
| Auto OFFのPNG復元 | 利用者確認：ON / Reference 7からOFF / Reference 5へ復元 |
| 復元後の再生成 | 00004が元のAuto画像と目視一致、Referenceの最小・平均・最大値も一致 |
| 手動4方式 | linear_distance=00002/00009、squared_distance=00010、root_distance=00011、absolute_sum=00012。方式名は利用者報告 |
| Autoから手動 | 00009と00002が目視一致 |
| 手動各方式からAuto | 00014と00004が目視一致、Auto統計も一致 |

途中のSkimmedCFG無効、Auto無効、Autoを非対応方式で使用した試行は、成功したAuto比較には含めない。画像の目視一致から画素単位の完全一致や画質改善を結論しない。手動4方式の実画像を旧版と比較したものでもない。

## 回帰テスト

事実：57件成功、スキップ0件。手動互換、観測処理、Auto予算、PNG復元関数、推論テンソル、診断、Linear Interpolation、ホスト参照2件を含む。ホスト由来コードの読み込みでSyntaxWarningが1件出たが、テストは成功した。

追加インストールは不要。PowerShellで既存環境を使用する：

```powershell
Set-Location '<reForge>\extensions\sd-webui-DifferenceCFG'
$env:PYTHONUTF8='1'
$env:DIFFCFG_HOST_REFERENCE='<reForge>\modules'
& '<reForge>\venv\Scripts\python.exe' -B -m unittest discover -s tests -p 'test_*.py' -v
```

新しい実行ログ：[REGRESSION_2026-11-17.log](REGRESSION_2026-11-17.log)。過去のテスト件数と合算しない。

## 未確認

画素単位の一致、一般的な画質改善、Hires.fix、LoRA、他モデル、広範な拡張併用、Forge ClassicのAuto、NeoのAuto、速度・VRAMの厳密な測定。Neoでは現行Autoは手動へ戻る。今回の結果から原設計の全公開判定条件を達成したとはしない。実験機能としての確認範囲を示す。

## ソースの照合

提示されたDifferenceCFG 5ファイル、SkimmedCFG 4ファイルは10月25日の保存基準版とSHA-256で一致。公開mainとの比較で既存の手動補正計算部分に変更なし。文書整理では実装ファイルを変更していない。