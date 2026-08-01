# Normalizer

## External Design

### 入力形式

拡張子でディスパッチするツリー（`contents/`、`definition/views/`）が受理する形式:

| 拡張子 | 扱い |
|---|---|
| `.yaml` / `.yml` / `.json` | レコードファイル（ルートは mapping） |
| `.md` | [prose](../40-communication/20-prose-spec.md)（`contents/` のみ） |
| その他 | [blob](../40-communication/30-blob-spec.md)（`contents/` のみ。`views_dir` では検証エラー） |

dotfile・dot ディレクトリ配下は形式によらず読まない。エディタ・VCS の cruft がソースツリーに同居できることを保証する側の要件で、形式ディスパッチに先行する。

**スコープ外: 固定名の定義ファイル** — `definition/schema.yaml` / `reports.yaml` / `sbdb.yaml` は `.json` にできない。`SourceLayout` が固定名で解決し `_verify_definition_entries` が未知エントリを弾く構造なので、拡張子の択一を許すのは別の変更になる。

### 背景: 手書きは YAML 推奨、JSON はワンショット機械出力の受け口

手書きソースは YAML を推奨する（Git 差分・エラー行指摘との親和性）。showcase に `.json` の例を置かないのはこのため。

JSON 入口の位置づけは、**フィードバックループを持たない機械的ワンショット出力** — LLM の構造化出力（constrained decoding は JSON 専用）・ビルドツール・cron — の contents 流用。反復できる書き手（人間・エージェント）はビルド検証がフィードバックループになるので YAML 側に居ればよい。実在のエクスポート JSON には封筒（メタデータキー）がほぼ必ず付くが、`additionalProperties: false` の下では schema.yaml に書き込むか前段の jq で剥がして受ける（実証は [L4 SBOM ドッグフーディング](node:/tasks/L/tasks/L4)）。JSONL・配列ルートは受理しない。

`docs/` の文言はこの用途を謳わず、制約（ルートは mapping）と推奨（YAML）のみを書く。用途は利用者が決めることで、ツールが宣言すると受理範囲の説明とは別の約束に読まれる。

## Internal Design

### `.json` は YAML 1.2 リーダで読む

`parse_mapping` は `.yaml` と `.json` を同じ ruamel リーダで読む。YAML 1.2 が JSON のスーパーセットで、`.lc` による位置情報もそのまま取れるため。厳密な JSON パーサに替えると `UserStr` / `Location` の位置情報タグ付け機構を二重に作ることになる — `query_deriver._diagnostic_from` は非 `UserStr` の offender を内部バグとして再 raise するので、位置情報を持たない入力経路は作れない。

外から見える帰結が 2 つある。`.json` ファイル内に YAML 記法を書いても通る（緩い方向のズレなので放置）。重複キーは JSON より厳しく `DuplicateKeyError` になる。

### 正規化スコープと catalog 境界

正規化スコープは catalog 化スコープと一致させる。境界外で walker が走ると、新規変換の追加で silent に壊れる latent risk が生じる。

- `content_normalizer`: user schema 全体が catalog 範囲 (`iter_normalized` で深く正規化)
- `query_deriver`: top-level dict のみが catalog 範囲 (`_iter_top_level` で dict→list 変換 + `normalize_query` による DSL の sugar→canonical 変換。catalog 化はしない)

### dict-pattern の synthetic id は常に string

`additionalProperties` を持つオブジェクトを `[{"id": <key>, ...}]` 配列に正規化する際、`id` は `str(key)` でコエースする。YAML は int/bool キー (`10:`) を natively 許すが、以下の理由で string に揃える:

1. **JSON は string キーしか持たない** — YAML キーは JSON 由来の正規化先には乗らない型を取りうるが、永続化形式 (`save_model` で書き出す JSON) は JSON 互換を保つ
2. **catalog 宣言が `id: string`** ([schema-spec.md](20-schema-spec.md) Entity 名節) — 宣言とデータ実体の型を一致させる
3. **x-ref ターゲット集合の型統一** — FK 検査が string-only で完結する (schema-schema は x-ref を type=string のみ許容)
4. **アンカーパス生成の一貫性** — entity ページのパス・アンカーパス生成器が常に string 入力を仮定できる

この normalization contract は user 向け reference には書かない (JSON 由来の自然な前提であり、明文化が逆にノイズになる)。surface したら `docs/reference/schema.md` の dict-pattern 節に注釈を足す。

## Proposals

### Unique 制約 (D8, D9)

追加の Unique 制約（id 以外のフィールドに対する一意性）の宣言。Phase 10 タスク [D8, D9](node:/tasks/D/tasks/D8)。
