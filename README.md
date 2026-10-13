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
