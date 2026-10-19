# Microsoft Store掲載文｜Folder Privacy Auditor｜レビュー準備稿
対象ブランチ: `ui/safe-product-upgrade-20261019`
状態: **文案完成 / 公開未承認 / Store ID・価格の実入力未済**
価格の仮設定: **¥1,480（条件付き・仮）**。正式価格・対応市場は権限のある販売者が承認し、Partner Centerで指定する。

## ja-JP
**製品名（候補）:** Folder Privacy Auditor

**短い説明:**
フォルダー内の検査可能な情報、要確認ファイル、未検査・失敗ファイルを分類して表示する読み取り専用ツールです。

**詳細説明（そのまま編集欄へ転記可能）:**
指定したフォルダー内のファイルを読み取り専用で調べ、個人情報に関連する文字列候補や検査できなかったファイルを整理します。要確認、検査範囲限定、未検査、失敗を絞り込んで見られ、監査レポートは全件保存します。

・指定フォルダーを読み取り専用で検査
・未検査・失敗・要確認を別々に表示
・全件を含むCSV・JSONレポート

**対応範囲と重要な注意事項:**
すべての文書・画像・Excel・PDF本文を深く検査するものではありません。検出ゼロは安全の証明ではありません。出力レポートにもファイル名等が含まれる場合があります。

**What's new:** 初回提出時は空欄。製品更新の場合のみ新旧の違いを事実確認して記載。

## en-US
**Suggested title:** Folder Privacy Auditor

**Short description:**
Review files in a folder, including flagged items, uninspected items and scan failures, without changing the originals.

**Full description:**
Inspect a selected folder without editing source files. Identify candidate patterns and files that could not be inspected. Filter results by review status while keeping the complete inventory in CSV and JSON reports.

• Read-only folder inventory
• Filter review, limited, uninspected and failed items
• Export complete CSV and JSON reports

**Important limitations:**
This is not a complete scan of all document, PDF, image or spreadsheet contents. A scan without findings does not prove a folder is safe. Reports may include sensitive paths and file names.

**What's new:** Leave blank for the initial submission.

## Partner Center 編集チェック
- 描写の対象は各製品の現行ブランチで**実装が確認できる機能のみ**。未知の機能や完全安全保証を足さない。
- 正式名の重複確認、年齢区分質問票、価格、カテゴリ、地域、検索キーワード、機能欄は提出画面で設定する。価格は購入実績の裏付けがない仮説。
- スクリーンショットは実機撮影5枚。本文に外部URL、HTML、未確認の商標や第三者との提携表現を入れない。
- 最終チェック: ユーザー向けの日本語/英語を実画面と照合。英語UIが未合格なら対応言語を無理に追加しない。
- ソースWindows QA、MSIX、Store Identity、プライバシー・サポート情報、ライセンス承認が揃うまで掲載しない。

公式: https://learn.microsoft.com/en-us/windows/apps/publish/publish-your-app/msix/add-and-edit-store-listing-info
