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

**決定: hidden エントリのスキップは全形式に統一する** — 現状 `_is_hidden` は blob 分岐でのみ効いており、dot ディレクトリ配下でも YAML / Markdown はパースされる。`.json` が YAML 側の経路に移ると、`.vscode/settings.json` のような「dot ディレクトリに居がちな JSON」がスキーマ検証に到達してビルドを落とす。dotfile が cruft であることは形式に依らないので、`load_source` の先頭で全形式一律にスキップする（既存挙動の変更を含む）。

**決定: `parse_yaml` は `parse_mapping` に改名する** — JSON を読む関数が `parse_yaml` のままでは呼び出し側を驚かせる。受理形式の列挙（`parse_yaml_or_json`）ではなく返り値の契約（ルート mapping を返す）で命名し、形式の増減に耐える。呼び出し側（schema_inspector / edition / manifest）はいずれも同じ契約で呼んでいる。

**決定: 手書きは YAML 推奨、JSON はワンショット機械出力の受け口** — showcase への `.json` contents 例は追加しない。手書きソースは YAML を推奨する（Git 差分・エラー行指摘との親和性）。JSON 入口の位置づけは、フィードバックループを持たない機械的ワンショット出力 — LLM の構造化出力（constrained decoding は JSON 専用）・ビルドツール・cron — の contents 流用。反復できる書き手（人間・エージェント）はビルド検証がフィードバックループになるので YAML 側。実在のエクスポート JSON には封筒（メタデータキー）がほぼ必ず付くが、`additionalProperties: false` の下では schema.yaml に書き込むか前段の jq で剥がして受ける（実証は [L4 SBOM ドッグフーディング](node:/tasks/L/tasks/L4)）。JSONL・配列ルートは対象外。docs の文言は用途を謳わず、制約（ルートは mapping）と推奨（YAML）のみを書く。

同期が要る箇所: blob の定義（「YAML・Markdown 以外」→ JSON を追加）、`docs/reference/` の入力形式記述（YAML 推奨の一文を含む）。

### Unique 制約 (D8, D9)

追加の Unique 制約（id 以外のフィールドに対する一意性）の宣言。Phase 10 タスク [D8, D9](node:/tasks/D/tasks/D8)。
