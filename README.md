# -Folder-Privacy-Auditor
    フォルダを指定すると、その中に何が入っているかを外部送信せず検査します。「個人情報らしきファイル」「暗号化されていないCSV」「大量の顧客データ」「重複ファイル」「隠しファイル」などを一覧化し、外部共有前の点検表を作ります。企業向けに発展させやすい商品です。


## 拡張: Storage Cause Analyzer（容量増加原因の調査）

従来のプライバシー監査とは独立した、読み取り専用の容量診断モジュールです。ファイル削除機能はありません。

- Windows GUI: `python storage_cause_gui.py`
- CLI: `python storage_cause_analyzer.py C:\\Users\\You\\Projects D:\\AuditReports`
- 前回との差分: `python storage_cause_analyzer.py C:\\Users\\You\\Projects D:\\AuditReports --baseline D:\\AuditReports\\storage_cause_XXXX\\storage_report.json`
- 分類: `.venv`、`node_modules`、`.git`、ビルド成果物、Pythonキャッシュ、一般キャッシュ、ダウンロード、その他
- 集計: 論理サイズの合計、最大50ファイル、第一階層別の内訳、前回からの増減
- シンボリックリンク・Windows再解析ポイントは追跡せず、スキップ数を表示
- エラー・未検査領域がある場合は `PARTIAL` と明示
- レポートは読み取り対象フォルダの**外**に新規生成
- テスト: `python -m unittest discover -s tests -p "test_storage_cause_analyzer.py" -v`

**制限**: 実ディスク占有量ではなくファイル論理サイズの合計です。NTFSの圧縮・ハードリンク・クラウドプレースホルダー・権限で読めない領域などを考慮していないため、Explorerの使用量と一致しない場合があります。カテゴリ分類は削除許可を意味しません。

Windows検証ビルド: `powershell -ExecutionPolicy Bypass -File .\\build-windows-validation.ps1`。
GitHub Actionsは手動実行のみ。Windowsでの完成検証・署名・販売審査は未完了。


## Windows QA evidence and manual acceptance (2026-10-13)

See [Windows QA Runbook](docs/WINDOWS_QA_RUNBOOK.md) for unsigned build verification, manual checks and local evidence. **This is not a sales release.**


## 2026-10-18: 容量履歴・前回比較の改善（独立開発ブランチ）

**基本操作は2か所を指定して1回クリック:** 調査フォルダとレポート保存先を選択し、「スキャン開始（読み取りのみ）」を押します。2回目以降は同じフォルダを対象にした最新の有効レポートを自動で探し、容量増減と分類別の差を表示します。必要な場合のみ「詳細」から比較するレポートを手動指定できます。

- 初回は比較対象なしと表示。結果が不足する場合は推定値として明示します。
- 別フォルダのレポート、不正なJSON、サイズ異常、リンク経由の履歴は比較対象外。
- 過去のレポート・調査フォルダのファイルは変更・削除しません。
- 論理ファイルサイズの比較であり、ディスクの物理使用量を保証しません。
- 既存のWindows GUI、テスト・QAスクリプト、フォーム等の他機能は保護したままです。

開発専用・販売HOLDです。コードに加えたテストは実行証拠が必要です。コマンド・受入基準は [容量履歴QAと販売ゲート](docs/STORAGE_HISTORY_QA.md) を参照してください。
