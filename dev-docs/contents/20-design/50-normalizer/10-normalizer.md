# Normalizer

contents 入力を検証し、辞書形式を配列形式に正規化する。Markdown ファイルは内蔵の prose スキーマに従って自動的に正規化する。参照整合性もチェックする。

受理する入力形式（拡張子ディスパッチ、dotfile の除外）は `docs/reference/cli.md` の Content and Views を正本とする。`.md` の扱いは [prose-spec](25-prose-spec.md)、それ以外の拡張子は [blob-spec](27-blob-spec.md) が設計を持つ。

## External Design

### 手書きは YAML 推奨、JSON はワンショット機械出力の受け口

手書きソースは YAML を推奨し、JSON 入口はフィードバックループを持たない機械的ワンショット出力の受け口と位置づける（[背景](../../90-appendix/20-design/50-normalizer/10-normalizer.md#手書きを-yaml-推奨とし-json-をワンショット機械出力の受け口とする理由)）。

`docs/` の文言はこの用途を謳わず、制約（ルートは mapping）と推奨（YAML）のみを書く。用途は利用者が決めることで、ツールが宣言すると受理範囲の説明とは別の約束に読まれる。謳わないのは説明を受理範囲に絞って読みやすくするためで、この用途を非推奨とする意図ではない。showcase で取り込みの例を見せるのは妨げない。

### dict-pattern の synthetic id は常に string

`additionalProperties` を持つオブジェクトを `[{"id": <key>, ...}]` 配列に正規化する際、string でないキーは `str()` でコエースする。YAML は int/bool キー (`10:`) を natively 許すが、以下の理由で string に揃える:

1. **JSON は string キーしか持たない** — YAML キーは JSON 由来の正規化先には乗らない型を取りうるが、永続化形式 (`save_model` で書き出す JSON) は JSON 互換を保つ
2. **カタログの宣言が `id: string`** ([schema-spec.md](../45-schema/10-schema-spec.md#データカタログ) データカタログ節) — 宣言とデータ実体の型を一致させる
3. **x-ref ターゲット集合の型統一** — FK 検査が string-only で完結する (schema-schema は x-ref を type=string のみ許容)
4. **アンカーパス生成の一貫性** — entity ページのパス・アンカーパス生成器が常に string 入力を仮定できる

この normalization contract は user 向け reference には書かない (JSON 由来の自然な前提であり、明文化が逆にノイズになる)。surface したら `docs/reference/schema.md` の dict-pattern 節に注釈を足す。

## Internal Design

### `.json` は YAML 1.2 リーダで読む

`parse_mapping` は `.yaml` と `.json` を同じ ruamel リーダで読む。YAML 1.2 が JSON のスーパーセットで、`.lc` による位置情報もそのまま取れるため。厳密な JSON パーサに替えると `UserStr` / `Location` の位置情報タグ付け機構を二重に作ることになる — `query_deriver._diagnostic_from` は非 `UserStr` の offender を内部バグとして再 raise するので、位置情報を持たない入力経路は作れない。

純 JSON リーダとは外から見える挙動が二つズレるが、どちらも放置する（[背景](../../90-appendix/20-design/50-normalizer/10-normalizer.md#純-json-リーダとのズレを放置する理由)）。

### Markdown は markdown-it-py で読む

Markdown AST は markdown-it-py（CommonMark 準拠、AST 走査で見出し抽出・リンク検出）。

## Proposals

### Unique 制約 (D8, D9)

追加の Unique 制約（id 以外のフィールドに対する一意性）の宣言。タスク [D8, D9](node:/tasks/D/tasks/D8)。

id 一意性の検査と同じ機構になる（集合をキーでグループ化して重複を報告する）。相違は宣言の出どころ（暗黙 / スキーマ宣言）と違反時の扱いで、宣言的 unique 制約は破れてもページは正常にレンダリングされるため、x-ref と同じく警告 + `--strict` 連動に収まる。

仕様確定時の検討事項:

- **複合キーは初版では落とす** — サロゲートキーへの移行が一般的で、複合キーによる join も未対応のため、単一キーで始める。検査器のキーをタプルで持っておけば後から広げられる
- **スコープの宣言** — id は「兄弟集合で一意」に確定しているが、根拠はアンカーパスが親で修飾されることなので、非 id 属性には転用できない。全 member を通じた一意性が要る属性を持つなら、そのオブジェクトは親のコンポジションではなくトップレベル entity であるべき、という整理もありうる
