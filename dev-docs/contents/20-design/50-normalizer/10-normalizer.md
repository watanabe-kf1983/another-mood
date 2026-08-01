# Normalizer

## Internal Design

### 正規化スコープと catalog 境界

正規化スコープは catalog 化スコープと一致させる。境界外で walker が走ると、新規変換の追加で silent に壊れる latent risk が生じる。

- `content_normalizer`: user schema 全体が catalog 範囲 (`iter_normalized` で深く正規化)
- `query_deriver`: top-level dict のみが catalog 範囲 (`_iter_top_level` で dict→list 変換 + `normalize_query` による DSL の sugar→canonical 変換。catalog 化はしない)

### dict-pattern の synthetic id は常に string

`additionalProperties` を持つオブジェクトを `[{"id": <key>, ...}]` 配列に正規化する際、`id` は `str(key)` でコエースする。YAML は int/bool キー (`10:`) を natively 許すが、以下の理由で string に揃える:

1. **JSON は string キーしか持たない** — YAML キーは JSON 由来の正規化先には乗らない型を取りうるが、永続化形式 (`save_model` で書き出す YAML) は JSON 互換を保つ
2. **catalog 宣言が `id: string`** ([schema-spec.md](20-schema-spec.md) Entity 名節) — 宣言とデータ実体の型を一致させる
3. **x-ref ターゲット集合の型統一** — FK 検査が string-only で完結する (schema-schema は x-ref を type=string のみ許容)
4. **アンカーパス生成の一貫性** — entity ページのパス・アンカーパス生成器が常に string 入力を仮定できる

この normalization contract は user 向け reference には書かない (JSON 由来の自然な前提であり、明文化が逆にノイズになる)。surface したら `docs/reference/schema.md` の dict-pattern 節に注釈を足す。

## Proposals

### 入力形式に JSON を追加 (M11)

`contents_dir` と `views_dir` で `.json` をデータファイルとして受理する（現状は YAML / Markdown 以外なので [blob](../40-communication/30-blob-spec.md) になる）。受理と同時に **`.json` は blob から外れる**。

**背景: なぜ必要か** — [M10](../40-communication/10-json-data-model.md#ステージ間中間表現を-json-へ-m10) がステージ間中間表現を `.json` にすると、blob-spec の「blob は定義上その拡張子を持ちえないので、レコードファイルと構造的に衝突しない」という論法が単独では崩れる。`.json` を入力データ形式にすれば同じ論法がそのまま成立し、blob のミラー経路に手を入れずに済む。M10 の前提タスク。

**背景: `.json` も ruamel で読む** — YAML 1.2 は JSON のスーパーセットなので、`parse_yaml` がそのまま JSON を解釈でき、`.lc` による位置情報も取れる。厳密な JSON パーサに替えると `UserStr` / `Location` の位置情報タグ付け機構を二重に作ることになり、`query_deriver._diagnostic_from` は非 `UserStr` の offender を内部バグとして再 raise するので、位置情報を持たない入力経路は作れない。帰結として `.json` ファイル内に YAML 記法を書いても通ってしまう（緩い方向のズレ）ほか、重複キーは JSON より厳しく `DuplicateKeyError` になる。

**スコープ外: 固定名の定義ファイル** — `definition/schema.yaml` / `reports.yaml` / `sbdb.yaml` は対象外。`SourceLayout` が固定名で解決し `_verify_definition_entries` が未知エントリを弾く構造なので、拡張子の択一は別の変更になる。拡張子でディスパッチするツリー（`contents/`、`definition/views/`）のみを対象とする。

同期が要る箇所: blob の定義（「YAML・Markdown 以外」→ JSON を追加）、`docs/reference/` の入力形式記述、showcase への入出力例。

### Unique 制約 (D8, D9)

追加の Unique 制約（id 以外のフィールドに対する一意性）の宣言。Phase 10 タスク [D8, D9](node:/tasks/D/tasks/D8)。
