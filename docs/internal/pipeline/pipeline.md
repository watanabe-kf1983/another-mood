# Pipeline

ユーザパイプラインとツール内部パイプラインの構成。

## ユーザパイプライン

ユーザの model/ から最終的なドキュメントを生成するパイプライン。
各ステージは StageRunner 経由で実行される（[stage-runner.md](stage-runner.md) 参照）。

```
model/
  schema/
  data/          → Normalizer → output/normalized/
  queries/                          ↓
                              Composer → output/views/
                                             ↓
presentation/                          Generator → output/documents/
  templates/                                            ↓
  paging.yaml                                     Hugo → output/rendered/
```

dev モードではステージ間のカスケードを Watcher が自動伝播する
（[process-coordination.md](process-coordination.md) 参照）。
build モードでは全段を直列実行する。

## ツール内部パイプライン

ユーザの views を、ツール内蔵テンプレートで可視化するパイプライン。
MS-Access のデータシートビューに相当する機能を提供する。

```
output/views/ （リードオンリー）
  → Generator（ツール内蔵テンプレート）
  → Hugo
```

- ユーザの output/ には一切書き込まない
- パススルー views によりテーブル一覧・中身を表示
- ユーザクエリの結果も同じように表示
- Composer は不要（views を直接参照）

ユーザ向け仕様は [meta-documentation.md](../../external/app/meta-documentation.md) を参照。