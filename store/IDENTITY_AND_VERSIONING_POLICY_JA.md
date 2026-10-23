# Folder Privacy Auditor — Identity正本・ビルダー連携・バージョン規則（2026-10-23）

## 実施範囲と開始点

- 作業元: `ui/safe-product-upgrade-20261019`
- 作業元HEADとの一致確認: `defd25ba587f2cfef0a00e283e679d9b9f21d1eb`
- 専用作業ブランチ: `fix/store-identity-json-20261023`
- main、作業元ブランチ、他製品、Partner Center本体には変更を加えない。
- この文書と正本JSONはPartner Centerのライブ照合を意味しない。

## 正本ファイルと初期ステータス

`store/partner-center-identity.json` が唯一の製品別Identityソースです。
再利用可能なスキーマは `store/partner-center-identity.schema.json` です。

| 項目 | 初期値 | 検証ステータス | 正本生成・公開への影響 |
|---|---|---|---|
| `store_id` | `9PKMCT98XQF5` | `OWNER_PROVIDED_UNVERIFIED` | Partner Centerの実画面と照合するまで正式ビルドをブロック |
| `display_name` | `Folder Privacy Auditor` | `SOURCE_FOUND_NOT_LIVE_VERIFIED` | 文書に記録された表示名。ライブの登録値と照合するまでブロック |
| `identity_name` | `null` | `UNKNOWN` | 会話内の画面表示は翻訳されているため正式なASCII文字列を断定できず、必須値不明としてブロック |
| `publisher` | `CN=46263F21-A700-41DB-8C9B-114C22FB82FC` | `OWNER_PROVIDED_UNVERIFIED` | 会話内の提供スクリーンショットに見える値。正本のソース記録には保存したが、今回のライブ照合は未実施なので正式ビルドをブロック |
| `publisher_display_name` | `null` | `UNKNOWN` | 画面の表示名は翻訳されている可能性があり、正確な登録値を得るまでブロック |
| `package_family_name` / `package_sid` | スクリーンショットから読み取った値 | `OWNER_PROVIDED_UNVERIFIED` | 会話内の製品Identity画面を出典として記録。ライブ照合は未実施。現行Manifest生成では直接使用しない |
| `application_version` | `null` | `UNKNOWN` | 内部アプリの版。パッケージ版から推測しない |
| `package_version` | `null` | `UNKNOWN` | 公開用MSIXの版。所有者の明示承認まで生成をブロック |

各項目には `source_refs` を保存します。値が不明な項目では、調べたソースがその値を確定していないことも記録し、推測をデータとして残しません。

## ビルダーとの連携

- `store/build-msix.ps1` は、外部の `IdentityName` / `Publisher` / `PublisherDisplayName` / `DisplayName` 引数を受け取りません。
- PowerShellビルダーは `store/identity_manifest.py` を呼び、正本JSONだけを読みます。
- `Package/Identity/Name`、`Package/Identity/Publisher`、`Package/Properties/PublisherDisplayName`、`Package/Properties/DisplayName` は、それぞれ正本フィールドへ直接対応します。アプリのVisualElements DisplayNameも同じ正本の表示名に一致させます。
- `store_id` はStore側の商品参照であり、ManifestのIdentity Nameへは転用しません。
- PFNとPackage SIDは現在のManifestに直接記述する値として扱いません。必要性や正確な値が別途確認された場合にのみ記録します。
- `-ValidateOnly` および `python store/identity_manifest.py --validate-only` は、JSON構造の検証を実行します。形式が正しくても出荷可能を意味せず、現在の設定は `FORMAL_MSIX=BLOCKED` を返します。
- 正式ビルドでは全ての必須値が指定の検証ステータスを満たし、パッケージ版が所有者承認済みである必要があります。未解決ならEXE・ロゴ・MakeAppxへ進む前に止まります。
- 正式Identityが確定するまでは、テスト用の合成Identityを本製品の正本へ書き込まないでください。合成値は一時的な単体テストのメモリ内だけでManifest値の割当を確認します。

## 共通スキーマv2への変更

共通Identityスキーマをv2へ更新する際、次を明確にしました。

1. `display_name` を必須の正本フィールドとして追加。
2. `display_name` にも値、`verification_status`、`source_refs` を要求。
3. 内部アプリの `application_version` とMSIXの `package_version` を別フィールドに分離。
4. すべての同一フィールドに検証ステータスを持たせ、未確認値をnullのまま記録可能とする。
5. `UNKNOWN` や未検証状態のままでも、JSONの構文・スキーマテストは実行可能にする。

これは共通スキーマの変更提案を具体化したものです。今回変更したのは対象のFolder Privacy Auditorリポジトリだけであり、他製品の正本JSONを一括変更していません。以後の製品へ適用する際は、その製品の専用作業ブランチで正規値と出典を個別に記録してください。

## MSIXパッケージバージョン規則

現行の製品ビルダーは、バージョン値を `1.0.0.0` として既定設定していました。これはビルドスクリプトの既定値にすぎず、Folder Privacy Auditorの公開承認済みバージョンを示す根拠はありません。その既定値を削除し、正本の `package_version.value` と `OWNER_APPROVED` ステータスがあるときだけ使用します。アプリ内部の版をパッケージ版に自動変換しません。

確認したMicrosoft公式資料：

- App package requirements / Package version numbering: https://learn.microsoft.com/en-us/windows/apps/publish/publish-your-app/msix/app-package-requirements#package-version-numbering
- 手動MSIX作成と `packagedClassicApp` の例: https://learn.microsoft.com/en-us/windows/msix/desktop/desktop-to-uwp-manual-conversion
- Desktop app packagingの説明: https://learn.microsoft.com/en-us/windows/apps/get-started/intro-pack-dep-proc

MicrosoftのPackage version numberingページは、Windows 10/11のUWPパッケージについて、4番目の要素がStore用に予約され、作成時に0でなければならないと説明しています。一方、対象のManifestは `Windows.Desktop` の `uap10:RuntimeBehavior="packagedClassicApp"` です。確認した公式資料の該当段落だけでは、この4番目の要素に関するUWP特有の説明を、`packagedClassicApp` に対する個別の規則としてまで断定できません。

そのため本作業では、既存ビルダーの厳格な制約を安易に緩和せず、プロジェクトの保守的ルールとして以下を維持します。

- 4要素の整数形式 `Major.Minor.Build.0`
- Majorは1以上
- 各要素は65535以下
- 第4要素は0
- 既定版なし。正本に明示され、`OWNER_APPROVED` のパッケージ版だけを用いる

これは既存条件を保守的に保持する実装方針であり、Partner Centerがそのパッケージを受理した証明ではありません。形式テストとライブの受理・公開履歴は別の判定です。`package_version` が未承認の現在は、正式MSIXを生成しません。

## 検証コマンド

クロスプラットフォームで実行可能：

```powershell
python store/identity_manifest.py --validate-only
python -m unittest discover -s tests -p "test_*.py" -v
```

Windows SDKがインストールされているか、正しいIdentity情報が登録されているかとは独立して、正本JSON、状態、値の割当ロジックとビルドゲートを検証します。

Windowsでは次も実行できます。

```powershell
.\store\build-msix.ps1 -ValidateOnly
```

期待結果：JSON構造検証はPASS、正式MSIXビルドはIdentity・バージョン未確定を理由にHOLD。
