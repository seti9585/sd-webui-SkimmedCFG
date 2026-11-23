> Historical record / 履歴資料：当時の実装・検証状況です。最新状況は [2026-11-17の検証記録](VALIDATION_2026-11-17.md) を参照してください。

# Auto Contract修復 — 2026-10-25

## 確認した不具合
変更前のSkimmedCFG観測コードは、処理後にcond._versionとuncond._versionを無条件で読み、
DifferenceCFGも同じ値を無条件で参照していました。
PyTorchの推論専用テンソルではこの属性へのアクセスが例外になります。

例外本文: Inference tensors do not track version counter.

観測側がERRORとなり、DifferenceCFGがAUTO_CONTRACT_INVALIDとして追加補正を見送ります。
旧ログは複数条件を同じ状態へまとめ、例外本文も捨てていたため、原因の判別ができませんでした。
前回までの試験は通常テンソルで、推論専用テンソルを作る実行条件を含めていませんでした。

## 根拠と確度
- 修正前の実ファイルを保全し、CPU上で通常モードとtorch.inference_modeを比較。
- 通常モードは観測APPLIED・AUTO_APPLIED、推論モードは観測ERROR/RuntimeError・AUTO_CONTRACT_INVALID。
- 具体的な失敗箇所はcond._versionで、例外本文まで再現。
- 16回を適用区間、14回を区間外とした模擬データでは、修正前はINVALID=16/GATE_OFF=14、
  修正後はAPPLIED=16/GATE_OFF=14。これは実機ログの再生ではなく、区間を設定した再現試験です。
- 実機で使われたテンソルの種類や例外本文は旧ログにないため、今回の実機原因が同一だったとの
  最終断定はできません。修正対象の不具合は再現で確認済みであり、実機症状の有力な原因です。
- 原典: https://docs.pytorch.org/docs/2.14/generated/torch.autograd.grad_mode.inference_mode.html
- 再現ログ: REPRODUCTION_BEFORE.txt

## 修復内容
通常テンソルは従来の更新番号検査を維持します。
推論専用テンソルは、SkimmedCFGの補正後に同じデバイス上へ値をコピーし、
DifferenceCFGが受け取った値と全要素が一致するか検査します。
検証を省略する修正ではありません。途中で値が変化した場合は追加補正を拒否します。
元テンソルと同じ実体・同じストレージの「コピー」は拒否します。
一時コピーは記録の消費・関数終了で解放され、生成をまたいで保持しません。

この方式はGPU上の一時コピーと比較演算を追加します。
比較結果は既存の一括統計転送に加え、追加のGPU→CPU同期は発生させません。
GPUでの速度やVRAM増分は未計測です。

Autoの計算式、Budgetの意味・初期値0.10、アルゴリズム識別子、
両拡張のcore.pyと既存補正本体は変更していません。
DIFF_GATE_OFFの判定も変更していません。

## 個別のContract診断
既存のAUTO_CONTRACT_INVALID総数に加え、DiffCFG Auto Contractへ理由を保存します。
コンソールは生成終了時にまとめて出力し、PNGのinfotext用生成情報へも保存します。
観測側例外には発生段階・例外型・本文を含めます。

主な理由:
- CHAIN_CONSUMER_MISSING / CHAIN_PRODUCER_COUNT / CHAIN_ORDER: フック構成・順序
- RECORD_MISSING / RECORD_VERSION: 観測記録の欠損・版
- PASS_TOKEN / PRODUCER_IDENTITY: sampling pass・作成者の取り違え
- SEQUENCE_CURRENT / SEQUENCE_REPLAY: 呼び出し番号・古い記録の再利用
- OUTPUTS_IDENTITY / INPUT_IDENTITY / COND_IDENTITY / UNCOND_IDENTITY: 別の予測
- SCALE_MISMATCH / SIGMA_MISMATCH / MODE_MISMATCH: 設定・実行値の取り違え
- OBSERVATION_ERROR: SkimmedCFG観測時の例外（段階・型・本文付き）
- STATE_INVALID: 想定外の観測状態
- SHAPE_RECORDED / SHAPE_PAIR / SHAPE_INPUT / DIMENSION / EMPTY_PREDICTION: 形状
- DTYPE_RECORDED / DTYPE_UNCOND / DTYPE_INPUT: 数値形式
- DEVICE_RECORDED / DEVICE_UNCOND / DEVICE_INPUT: デバイス
- GUARD_VERSIONS_MISSING / GUARD_SNAPSHOTS_INVALID: 検査情報の欠損
- COND_VERSION / UNCOND_VERSION: 通常テンソルの途中変更
- COND_SNAPSHOT_MISSING / UNCOND_SNAPSHOT_MISSING: 推論テンソルの検査コピー欠損
- COND_SNAPSHOT_INVALID / UNCOND_SNAPSHOT_INVALID: コピーの形状等の不整合・共有ストレージ
- COND_CONTENT_CHANGED / UNCOND_CONTENT_CHANGED: 推論テンソルの途中変更
- CONTRACT_EXCEPTION: その他の例外（発生段階・型・本文付き）

DiffCFG Auto Guardは、成功した受け渡し検査の方式別回数です。
INFERENCE_SNAPSHOTは推論テンソル用の値比較、VERSION_COUNTERは通常の更新番号比較です。
これらはAUTO_APPLIEDの回数とは異なり、検査後に追加補正を見送る回も含みます。
参照値統計は引き続きAUTO_APPLIEDだけを対象とします。

## 回帰試験
47項目PASS（Python 3.13 / PyTorch 2.14.1+cpu）。
- 32種類のContract条件を個別に壊し、期待する理由コードで拒否することを確認。
- 推論テンソルのcond/uncond書き換え、コピー欠損、共有ストレージを拒否。
- 通常テンソルと推論テンソルの32条件で、修正後の出力とReferenceが完全一致。
- 通常経路の既存Auto96条件で改修前と完全一致。
- 手動経路、既存Single Scale/Linear Interpolation、統計リセット等の回帰試験もPASS。
- 正常適用時のCPU値取得回数は通常/推論ともfloat=2、bool=3、tolist=2。
  item/cpu/numpyの追加呼び出しなし。実GPU同期の計測ではなくコードとCPU試験による確認。
- 両拡張のcore.pyが修正前とバイト一致することを確認。
- 実機での新しい生成結果、画質、速度、保存PNGの確認は未実施。

## 実機での確認
両拡張を更新した後、WebUIを完全に終了・再起動してください。
CFG20 / Linear Interpolation3 / DifferenceCFG linear_distance / Auto ON / Budget0.10を維持して再生成します。
AUTO_APPLIEDが増えて参照値統計のcountが正になるか確認してください。
失敗が残る場合はDifferenceCFG Auto Contractの理由付き行を確認します。
INFERENCE_SNAPSHOTの記録があれば、実機でも今回修復した検査方式が使われています。
なお、今回の設定でも実際の予測値によって補正を見送る場合があるため、
実機で必ずAUTO_APPLIED=16になるとは保証しません。

## 開発用の再試験
通常利用に追加のライブラリは不要です。開発用に再試験する場合のみ:
- 導入: python -m pip install torch --index-url https://download.pytorch.org/whl/cpu
- DifferenceCFGフォルダで実行:
  python -X utf8 -B -m unittest discover -s tests -p "test_*.py" -v

## ライセンス・典拠
各拡張のLICENSEとNOTICEを維持。
PyTorchの推論モード仕様を根拠とし、今回の修復は観測と検査の受け渡し層に限定します。
