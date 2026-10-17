# 容量履歴の検証手順・Microsoft Store販売ゲート

対象ブランチ: `improve/storage-history-20261018`。mainを上書きしない。

## Windowsで実行する検証

GitHub Actionsがステップ前に失敗している場合、コードがPASSしたとは扱わない。
次のコマンドを当該ブランチの作業ディレクトリで実行する。

```powershell
py -3 -m compileall -q storage_cause_analyzer.py storage_history.py storage_cause_gui.py tests
py -3 -m unittest discover -s tests -p "test_*.py" -v
py -3 .\storage_cause_gui.py --smoke-test --smoke-output ui-proof.json
py -3 .\storage_cause_gui.py --e2e-test gui-e2e-proof.json
```

### 確認基準
- 初回に `comparison_status=NOT_COMPARED` を記録し、比較値を生成しない。
- 2回目は同一フォルダーの過去レポートだけを使う。データ増減はMiB/GiB表示。
- 明示的な比較対象指定は自動選択より優先。
- 先行結果がPARTIALなら `growth_warning` を表示する。
- JSON破損、別フォルダー、シンボリックリンク、巨大な履歴、権限エラーは誤った比較に使わない。
- 元データ・過去レポートを変更・削除しない。
- Windows 10/11で日本語パス、画面倍率100/125/150%、キーボード操作、ウィンドウ縮小を実機確認。
- 既存 `build-windows-validation.ps1` と `qa/windows-acceptance.ps1` の動作も回帰確認し、試験用MSIXを販売版と混同しない。
- CIのLinuxとWindows双方でrunner割当なし・`steps=[]`の場合、まずGitHub Actionsの利用制限・runner割当・課金設定・GitHubサービス障害を確認する。コードのPASS/FAILは未判定。

## 収益化の判断基準

現時点の判定は **HOLD**。ソフトとしての価値は「容量が何で増えたか」「前回から何が増えたか」を削除なしで短時間に確認できる点。

1. 実データで速度・誤差・原因分類を検証。未知の内容や再解析ポイントは隠さない。
2. GUI検証完了後、既存Folder Privacy Auditorと別商品にするか追加機能にするかを販売価値・保守費用・重複の観点で判断。安易に有料製品を増やさない。
3. 商用ライセンス・依存関係・プライバシー説明・アクセシビリティ・簡潔な画面画像と説明文を整備。
4. 正式なStore IDでMSIX作成、署名・インストール・アップデート・アンインストール・認定を完了。
5. 価格は現在の競合比較と購入便益の証拠に基づいて決める。データ削除効果や完全な監査を保証しない。

この検証ブランチは既存mainに自動統合しない。
