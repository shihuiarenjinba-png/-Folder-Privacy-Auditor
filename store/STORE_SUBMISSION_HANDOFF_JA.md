# Folder Privacy Auditor — Microsoft Store提出準備・商品情報案
**開発中 / 未承認 / リリースHOLD。** 改良ブランチ `ui/safe-product-upgrade-20261019` の**現時点の機能だけ**を記載。正規Package Identity・Store ID・価格・年齢区分は、Partner Centerの実記録で確定し、架空データを記載しない。

## 提案する商品説明（日本語）
フォルダー内のファイル数、容量、個人情報候補、未検査ファイルを読み取り専用で確認し、CSV・JSONのレポートを作成します。

主な特徴：
- フォルダーを指定するだけで読み取り専用検査
- 要確認・未検査・失敗を絞り込んで表示
- 全件を保持するCSV・JSONレポート

制限・注意：
PDF・画像・Excelなどの内部情報を網羅的に解析する機能はありません。検出ゼロでも安全を保証しません。

### 候補価格
1,480円（条件付き仮説・未承認）。**実際の購入データによる実証ではない。** 商品登録前に商業性・QA・顧客価値を再判定する。無料候補でも品質・権利審査は必須。

## 画面キャプチャ — 本物のWindows起動画面からのみ取得
- 対象: Windows Desktopのみ。JPEG画像をPNGへ変換した代替物、モック、別製品のUIを提出しない。
- Microsoft公式: 最低1枚、4枚以上推奨、最大10枚。PNG、**1366×768以上**、各50MB以下。
- 販売用推奨: **5枚**。次の手順を実機で実行して撮影し、初期ファイル名は `store-assets/screenshots/ja-JP/01.png` ～ `05.png` とする（保存先のディレクトリはWindows担当が新規作成）。
1. `01.png` — フォルダーの選択
2. `02.png` — 検査完了の件数サマリー
3. `03.png` — 要確認項目の絞り込み
4. `04.png` — 未検査項目の一覧
5. `05.png` — CSV・JSONレポートの保存結果
- 英語表示に実際に対応し、QA済みの場合のみ en-US の5枚を同様に撮影。未完成の英語UIを売り物にしない。
- 個人情報を含まない**合成テストデータ**のみ表示。起動EXEのSHA、リポジトリコミットSHA、撮影解像度、実機OS、表示倍率を別ログに記録。

## MSIX / Identity正本
1. 対象ブランチの正本 `store/partner-center-identity.json` とスキーマ `store/partner-center-identity.schema.json` を使用する。Identity値をビルド引数や環境変数で二重管理しない。
2. 現在の正本は部分的な情報しか確定していない。Store ID `9PKMCT98XQF5` は `OWNER_PROVIDED_UNVERIFIED`、表示名 `Folder Privacy Auditor` は `SOURCE_FOUND_NOT_LIVE_VERIFIED`。Identity Name、Publisher、Publisher Display Name、パッケージ版は現時点で `null / UNKNOWN`。Partner Centerの実記録で正確な値を確認するまで、正本に推測値を入れない。
3. 正本構造の検証は `python store/identity_manifest.py --validate-only` または Windows 上の `.\store\build-msix.ps1 -ValidateOnly` で行える。JSON構造が有効でも `FORMAL_MSIX=BLOCKED` は正常な安全ゲートである。
4. 正式な Identity Name、Publisher、Publisher Display Name、Store ID、表示名が Partner Center の登録値と照合され、正本の適切なステータスに更新され、パッケージ版が明示的に承認された場合に限り、ビルダーを次の形式で使用する。
   ```powershell
   .\store\build-msix.ps1 -ExePath "<path-to-FolderPrivacyAuditor.exe>" -AssetsDirectory "<approved-assets-directory>"
   ```
   Identityやバージョンをコマンドライン引数で渡すことはできない。ビルダーは正本JSONだけを読み取る。既定の `1.0.0.0` はない。
5. 実際に商用利用権を持つ `StoreLogo.png` (50×50)、`Square44x44Logo.png` (44×44)、`Square150x150Logo.png` (150×150) を `store-assets/assets/` に用意する。ダミー画像禁止。
6. 生成MSIXは**提出候補であり販売承認ではない**。このビルダーは署名・アップロード・公開を行わない。ストア提出用署名とローカルサイドロード検証の署名要件を混同しない。
7. クリーンWindows 10/11でインストール/起動/保存/再起動/更新/削除/容量不足・権限拒否を実際に検査する。最新SDKでWACKが利用できる場合は補助実施。
8. 商用利用権・OSSライセンス/NOTICE/SBOM、プライバシー・サポート情報の実在性を確認する。
9. 商品説明、Screenshots、ロゴ、カテゴリ、年齢区分、価格と提供地域をPartner Centerへ入力してドラフトを完成させる。**承認なしでSubmit/Publishはしない**。

## 禁止事項・提出ゲート
- 既存main、引継ぎ済み4製品、Store ID登録済み8製品へ直接マージ・上書きしない。
- MSIX署名/インストール・実ページ記録・QA未実施をPASS扱いしない。
- Windows CI 0ステップ実行失敗は「未実施」。Windowsテストログと撮影した正真正銘のスクリーンショットが必要。
- 本文で未対応機能を購入可能な機能として宣伝しない。
- 公開・課金の最終承認にはWindows実機ログ、第三者権利、Storeドラフト確認、Microsoft認定結果が必要。

公式: https://learn.microsoft.com/en-us/windows/apps/publish/publish-your-app/msix/create-app-submission
公式画像規定: https://learn.microsoft.com/en-us/windows/apps/publish/publish-your-app/msix/screenshots-and-images
公式署名: https://learn.microsoft.com/en-us/windows/apps/publish/publish-your-app/msix/app-package-requirements
