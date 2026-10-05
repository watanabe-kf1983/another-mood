# Normalizer

## External Design

### 入力形式

> **[W4 dup]** 表と dotfile 規則 ↔ cli.md:49,53 (b, 理由まで同文)、source_loader.py:73-80、file_type.py:1-8 (a) — 完全。約束。案: 削除→docs。「スコープ外: 固定名の定義ファイル」は残す

拡張子でディスパッチするツリー（`contents/`、`definition/views/`）が受理する形式:

| 拡張子 | 扱い |
|---|---|
| `.yaml` / `.yml` / `.json` | レコードファイル（ルートは mapping） |
| `.md` | [prose](../40-communication/20-prose-spec.md)（`contents/` のみ） |
| その他 | [blob](../40-communication/30-blob-spec.md)（`contents/` のみ。`views_dir` では検証エラー） |

dotfile・dot ディレクトリ配下は形式によらず読まない。エディタ・VCS の cruft がソースツリーに同居できることを保証する側の要件で、形式ディスパッチに先行する。

**スコープ外: 固定名の定義ファイル** — `definition/schema.yaml` / `reports.yaml` / `sbdb.yaml` は `.json` にできない。`SourceLayout` が固定名で解決し `_verify_definition_entries` が未知エントリを弾く構造なので、拡張子の択一を許すのは別の変更になる。

### 背景: 手書きは YAML 推奨、JSON はワンショット機械出力の受け口

> **[W4 → appendix?]** 推奨: 移す

手書きソースは YAML を推奨する（Git 差分・エラー行指摘との親和性）。手書きの例として showcase に `.json` を置かないのはこのため（機械出力の取り込み例である SBOM showcase は別）。

JSON 入口の位置づけは、**フィードバックループを持たない機械的ワンショット出力** — LLM の構造化出力（constrained decoding は JSON 専用）・ビルドツール・cron — の contents 流用。反復できる書き手（人間・エージェント）はビルド検証がフィードバックループになるので YAML 側に居ればよい。実在のエクスポート JSON には封筒（メタデータキー）がほぼ必ず付くが、`additionalProperties: false` の下では schema.yaml に書き込むか前段の jq で剥がして受ける（実例は `showcase/sbom`）。JSONL・配列ルートは受理しない。

`docs/` の文言はこの用途を謳わず、制約（ルートは mapping）と推奨（YAML）のみを書く。用途は利用者が決めることで、ツールが宣言すると受理範囲の説明とは別の約束に読まれる。謳わないのは説明を受理範囲に絞って読みやすくするためで、この用途を非推奨とする意図ではない。showcase で取り込みの例を見せるのは妨げない。

## Internal Design

### `.json` は YAML 1.2 リーダで読む

> **[W4 dup]** ↔ source_loader.py:95-96、query_deriver.py:229-237 (a, 部分)。案: 残す (設計判断+帰結)。DuplicateKeyError の帰結はコードに無い→コードへ

`parse_mapping` は `.yaml` と `.json` を同じ ruamel リーダで読む。YAML 1.2 が JSON のスーパーセットで、`.lc` による位置情報もそのまま取れるため。厳密な JSON パーサに替えると `UserStr` / `Location` の位置情報タグ付け機構を二重に作ることになる — `query_deriver._diagnostic_from` は非 `UserStr` の offender を内部バグとして再 raise するので、位置情報を持たない入力経路は作れない。

外から見える帰結が 2 つある。`.json` ファイル内に YAML 記法を書いても通る（緩い方向のズレなので放置）。重複キーは JSON より厳しく `DuplicateKeyError` になる。

### 正規化スコープと catalog 境界

> **[W4 dup]** ↔ query_deriver.py _iter_top_level docstring (a, 部分)。案: 残す (不変条件)

正規化スコープは catalog 化スコープと一致させる。境界外で walker が走ると、新規変換の追加で silent に壊れる latent risk が生じる。

- contents: user schema 全体が catalog 範囲（`iter_normalized` で深く正規化）
- views: catalog 境界は top-level で止まる（`_iter_top_level` の dict→list 変換と `normalize_query` の sugar→canonical 変換まで）。クエリ本体（`where:` の AST 等）は catalog データではないので正規化しない

### dict-pattern の synthetic id は常に string

> **[W4 dup]** ↔ normalize_core.py:96-99 (理由 3/4)、schema-schema.yaml:178-182 (a)、20-schema-spec 書ける位置:48 (c) — 完全。案?: 不変条件なので design に残し、コード側コメントを縮める。schema-spec 側の再掲はポインタ化

`additionalProperties` を持つオブジェクトを `[{"id": <key>, ...}]` 配列に正規化する際、string でないキーは `str()` でコエースする。YAML は int/bool キー (`10:`) を natively 許すが、以下の理由で string に揃える:

1. **JSON は string キーしか持たない** — YAML キーは JSON 由来の正規化先には乗らない型を取りうるが、永続化形式 (`save_model` で書き出す JSON) は JSON 互換を保つ
2. **catalog 宣言が `id: string`** ([schema-spec.md](20-schema-spec.md) Entity 名節) — 宣言とデータ実体の型を一致させる
3. **x-ref ターゲット集合の型統一** — FK 検査が string-only で完結する (schema-schema は x-ref を type=string のみ許容)
4. **アンカーパス生成の一貫性** — entity ページのパス・アンカーパス生成器が常に string 入力を仮定できる

この normalization contract は user 向け reference には書かない (JSON 由来の自然な前提であり、明文化が逆にノイズになる)。surface したら `docs/reference/schema.md` の dict-pattern 節に注釈を足す。

## Proposals

### Unique 制約 (D8, D9)

追加の Unique 制約（id 以外のフィールドに対する一意性）の宣言。タスク [D8, D9](node:/tasks/D/tasks/D8)。

id 一意性の検査と同じ機構になる（集合をキーでグループ化して重複を報告する）。相違は宣言の出どころ（暗黙 / スキーマ宣言）と違反時の扱いで、宣言的 unique 制約は破れてもページは正常にレンダリングされるため、x-ref と同じく警告 + `--strict` 連動に収まる。

仕様確定時の検討事項:

- **複合キーは初版では落とす** — サロゲートキーへの移行が一般的で、複合キーによる join も未対応のため、単一キーで始める。検査器のキーをタプルで持っておけば後から広げられる
- **スコープの宣言** — id は「兄弟集合で一意」に確定しているが、根拠はアンカーパスが親で修飾されることなので、非 id 属性には転用できない。全 member を通じた一意性が要る属性を持つなら、そのオブジェクトは親のコンポジションではなくトップレベル entity であるべき、という整理もありうる
