# Pipeline

ユーザの定義・コンテンツから最終的なドキュメントを生成するパイプライン。

| ステージ | User Input | Upstream | Output |
|---|---|---|---|
| inspect_schema | schema_dir | — | inspect_schema_dir |
| normalize_contents | contents_dir, schema_dir ※1 | inspect_schema_dir | normalize_contents_dir |
| normalize_queries | queries_dir | inspect_schema_dir | normalize_queries_dir |
| compose | — | inspect_schema_dir ※2, normalize_contents_dir, normalize_queries_dir | compose_dir |
| generate | templates_dir | compose_dir | generate_dir |
| reconcile | — | generate_dir | reconcile_dir |
| render | — | reconcile_dir | render_dir |

dev モードでは User Input / Upstream ディレクトリの変更を Watch してステージを自動再実行する（`pipeline/base.py` 参照）。build モードでは依存順に直列実行する。※印は Watch 対象外の Input:

Upstream は前段ステージの Output であり、`BuildReport`（エラー伝播）の収集対象。User Input はユーザが直接編集するディレクトリで、`BuildReport` の収集対象外。

- ※1 schema_dir: バリデーションルールの読み込みに使うが、変更は SchemaInspector → inspect_schema_dir の経路で伝播するため Watch 不要
- ※2 inspect_schema_dir: 変更は SchemaInspector → inspect_schema_dir → Normalizer(contents) → normalize_contents_dir とカスケードし、normalize_contents_dir の変更で Composer が Kick されるため Watch 不要