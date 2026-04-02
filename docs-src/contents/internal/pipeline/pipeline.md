# Pipeline

ユーザの定義・コンテンツから最終的なドキュメントを生成するパイプライン。

| ステージ | コンポーネント | User Input | Upstream | Output |
|---|---|---|---|---|
| Inspect Schema | SchemaInspector | schemaDir | — | dataCatalogDir |
| Normalize Contents | Normalizer | contentsDir, schemaDir ※1 | dataCatalogDir | normalizedContentsDir |
| Normalize Queries | Normalizer | queriesDir | dataCatalogDir | normalizedQueriesDir |
| Compose | Composer | — | dataCatalogDir ※2, normalizedContentsDir, normalizedQueriesDir | viewsDir |
| Generate | Generator | templatesDir | viewsDir | outDir |
| Render | Renderer | — | outDir | render.outDir |

dev モードでは User Input / Upstream ディレクトリの変更を Watch してステージを自動再実行する（`pipeline/base.py` 参照）。build モードでは依存順に直列実行する。※印は Watch 対象外の Input:

Upstream は前段ステージの Output であり、`BuildReport`（エラー伝播）の収集対象。User Input はユーザが直接編集するディレクトリで、`BuildReport` の収集対象外。

- ※1 schemaDir: バリデーションルールの読み込みに使うが、変更は SchemaInspector → dataCatalogDir の経路で伝播するため Watch 不要
- ※2 dataCatalogDir: 変更は SchemaInspector → dataCatalogDir → Normalizer(contents) → normalizedContentsDir とカスケードし、normalizedContentsDir の変更で Composer が Kick されるため Watch 不要