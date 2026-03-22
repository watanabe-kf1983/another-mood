# Pipeline

ユーザパイプラインとツール内部パイプラインの構成。

## ユーザパイプライン

ユーザの定義・コンテンツから最終的なドキュメントを生成するパイプライン。
各ステージは AtomicDirWriter 経由で実行される（[stage-runner.md](stage-runner.md) 参照）。

```
schemaDir   → Normalizer → normalizedSchemaDir
                                ↓ (watch)
schemaDir ─────────┐
contentsDir ───────┼→ Normalizer → normalizedContentsDir
                   │
queriesDir  → Normalizer → normalizedQueriesDir

normalizedSchemaDir ────┐
normalizedContentsDir ──┼→ Composer → viewsDir
normalizedQueriesDir ───┘                ↓
templatesDir                      Generator → outDir
profilesFile                                     ↓
                                            Hugo → render.outDir
```

### Normalizer の3回呼び出し

Normalizer は入力ディレクトリの種類ごとに独立したステージとして3回実行される。
各呼び出しの Input（processFn が読むデータ）と Watch（Watcher の監視対象）は異なる。

| Normalize 対象 | 検証対象 (Input, Watch) | 検証用スキーマ (Input) | 検証用スキーマ検証結果 (Watch) |
|---|---|---|---|
| schema | schemaDir | ツール内蔵 SchemaSchema | なし（空振り） |
| contents | contentsDir | schemaDir | normalizedSchemaDir |
| queries | queriesDir | ツール内蔵 QuerySchema | なし（空振り） |

- **検証対象**: Normalizer が検証・正規化するデータ。Input であり Watch 対象でもある
- **検証用スキーマ**: 検証に使うスキーマ。Input だが実行時に変化しない（ツール内蔵）か、
  変更が別経路（検証用スキーマ検証結果）で伝播するため、Watch 対象に含めない
- **検証用スキーマ検証結果**: 検証用スキーマ自体が正しいかの検証結果。
  contents の Normalize のみ、schemaDir がユーザ定義であるため normalizedSchemaDir を
  Watch して上流エラーを検知する。schema / queries はツール内蔵スキーマで検証するため空振り

エラー伝播の詳細は [process-coordination.md](process-coordination.md) を参照。

### Composer

Composer は正規化済みの3ディレクトリのみを入力とする。
生の queriesDir は参照しない。

| Input | Watch |
|---|---|
| normalizedSchemaDir, normalizedContentsDir, normalizedQueriesDir | normalizedContentsDir, normalizedQueriesDir |

Composer が normalizedSchemaDir を Watch しない理由:
schemaDir の変更は Normalizer(schema) → normalizedSchemaDir → Normalizer(contents) →
normalizedContentsDir とカスケードし、normalizedContentsDir の変更で Composer が Kick される。

dev モードではステージ間のカスケードを Watcher が自動伝播する
（[process-coordination.md](process-coordination.md) 参照）。
build モードでは依存順に直列実行する。

## ツール内部パイプライン

ユーザの views を、ツール内蔵テンプレートで可視化するパイプライン。
MS-Access のデータシートビューに相当する機能を提供する。

```
viewsDir （リードオンリー）
  → Generator（ツール内蔵テンプレート） → meta.outDir
  → Hugo → meta.render.outDir
```

- ユーザの出力ディレクトリには一切書き込まない
- パススルー views によりテーブル一覧・中身を表示
- ユーザクエリの結果も同じように表示
- Composer は不要（views を直接参照）

ユーザ向け仕様は [meta-documentation.md](../../external/app/meta-documentation.md) を参照。