# Refactor Plan: Pipeline Dir 名 snake_case 統一

このブランチは作業プレースホルダ。実着手時にこの REFACTOR_PLAN.md は削除する。

## 背景

internal/external doc では各ステージの入出力ディレクトリを `viewsDir`、`dataCatalogDir`、`normalizedContentsDir` 等の descriptive な camelCase 論理名で記述している。これらは元々ユーザが個別に設定可能なディレクトリとして config-spec.md に定義されていたが、その後「ユーザに設定させる必要がない」と判断されて config.py からは削除された。doc 側の更新が漏れて descriptive 名だけが残っている状態。

実装側は `tmp_subdir(stage.name)` で動的にサブディレクトリを作るため、実体は `tmp/inspect_schema/`、`tmp/compose/`、`tmp/generate/` のようにステージ名（= 関数名、snake_case）ベースになっている。

doc と impl が乖離しているので、doc を impl に合わせて snake_case に統一する。

## 方針

- 全 Dir 名を snake_case に統一し、impl の関数名 / Python 属性とそのまま grep でクロスリファレンスできる状態にする
- User Input 側の Dir 名（`schemaDir` 等）も同時に snake_case 化（`schema_dir`）
- impl 側でも `tmp_subdir("render_output")` を `tmp_subdir("render")` にリネームし、Stage 名と統一

## 結果イメージ（pipeline.md のステージ表）

| ステージ | User Input | Upstream | Output |
|---|---|---|---|
| inspect_schema | schema_dir | — | inspect_schema_dir |
| normalize_contents | contents_dir, schema_dir ※1 | inspect_schema_dir | normalize_contents_dir |
| normalize_queries | queries_dir | inspect_schema_dir | normalize_queries_dir |
| compose | — | inspect_schema_dir ※2, normalize_contents_dir, normalize_queries_dir | compose_dir |
| generate | templates_dir | compose_dir | generate_dir |
| reconcile | — | generate_dir | reconcile_dir |
| render | — | reconcile_dir | render_dir |

## リネームマッピング

| 旧 | 新 |
|---|---|
| `schemaDir` | `schema_dir` |
| `contentsDir` | `contents_dir` |
| `queriesDir` | `queries_dir` |
| `templatesDir` | `templates_dir` |
| `dataCatalogDir` | `inspect_schema_dir` |
| `normalizedContentsDir` | `normalize_contents_dir` |
| `normalizedQueriesDir` | `normalize_queries_dir` |
| `viewsDir` | `compose_dir` |
| (新規) | `generate_dir` |
| (新規) | `reconcile_dir` |
| `render.outDir` | `render_dir` |

注: `generate_dir` と `reconcile_dir` は Reconcile 追加 PR (refactor/split-reconcile) で `generatedDir`、`reconciledDir` という暫定 camelCase 名で先行投入されるため、本リネーム PR ではそれらも snake へ置換する。

## 影響範囲

### internal doc

- docs-src/contents/internal/pipeline/pipeline.md
- docs-src/contents/internal/architecture.md
- docs-src/contents/internal/components/composer.md
- docs-src/contents/internal/components/schema-inspector.md
- docs-src/contents/internal/components/normalizer.md
- docs-src/contents/internal/components/generator.md
- docs-src/contents/internal/components/renderer.md

### external doc

- docs-src/contents/external/app/config-spec.md（廃止済みの行を削除 + 残す行の整理）
- docs-src/contents/external/app/project-structure.md
- docs-src/contents/external/app/meta-documentation.md
- docs-src/contents/external/composer/queries-spec.md
- docs-src/contents/external/normalizer/schema-spec.md
- docs-src/contents/external/generator/template-spec.md
- docs-src/definition/templates/data-catalog.md

### impl

- src/reqs_builder/pipeline/stages.py（`render_input` → `render_input`、`render_output` → `render` のリネーム検討）
- src/reqs_builder/pipeline/render.py（`render_input_dir`、`render_output_dir` 引数名の見直し）

## 確認事項（着手時）

- config-spec.md に残っている廃止済みの設定キー行（`dataCatalogDir`、`normalizedContentsDir`、`normalizedQueriesDir`、`viewsDir` の RB_*_DIR）を全部削除して良いか
- profile 関連の TOBE 記述（generator.md の `outDir/{profile_name}/` 等）は今回の rename と合わせて `generate_dir/{profile_name}/` に書き換えるか、TOBE のまま放置するか
