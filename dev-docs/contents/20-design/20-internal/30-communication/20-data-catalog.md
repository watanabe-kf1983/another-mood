# データカタログ

## 定義

**データカタログ**（以下カタログ）は、スキーマから起こした entity と attribute の目録。`inspect_schema` が `definition/schema.yaml` を meta-schema で検証したうえで起こし、JSON で永続化する（[ステージ構成](../20-pipeline.md#ステージ構成)の `inspect_schema/`）。

一つの目録に三つの出自の entity が載る:

- 利用者のスキーマの entity
- 内蔵スキーマ（prose / blob）の entity
- カタログ自身の形を記述する `__definition` の entity。クエリが `from: __definition.entities` でカタログを読むための自己記述

後段のステージは、スキーマの構造を知りたいときにスキーマを読み直さず、カタログを読む:

- `normalize_contents` — x-ref のデータ検査（`data_fk_validator.py`）。ただし contents の検証と map → array の正規化は JSON Schema そのものを使うので、このステージだけはスキーマファイルも読む。スキーマは監視しないので、スキーマの変更は `inspect_schema/` の更新として届く
- `derive_queries` — `from:` の解決と、ビューから派生する entity の生成。派生 entity を加えたカタログを出力する
- `compose` — カタログをそのまま下流へ通す
- `generate` — メタドキュメント（`__db/`）の描画と、レコードの出自（内蔵の prose / blob か）の判別
- `tap_schema`（`mood tap --schema`）— カタログから tap 文書の JSON Schema を書き出す

## compose の出力は、カタログが宣言した形に一致する

クエリの各句は、レコード変換（`apply`）とカタログの変換（`derive`）を同じ DSL 断片から対で持つ（`components/shared/query.py`）。`derive_queries` は `derive` でビューの出力の形を派生 entity としてカタログに載せ、`compose` は同じ `Query` の `apply` でレコードを作る。

両者は同じ順で同じ句を通り、句ごとの対が整合しているので、compose の出力は derive_queries が宣言した形に一致する。下流（`generate` のメタドキュメント、`tap_schema`）はデータを見ずにカタログを信じてよい。句を足すときは両方を対で足す。

## 形

形は `components/shared/data_catalog.py` に定義する。表現は二つあり、Node / Edge の木が正の表現で、Entity の列はその平坦な直列化。ステージ間はこの列を JSON で受け渡す。木は `derive_queries` が要る: ビューの `from:` が指す部分木を切り出し、派生 entity としてルートの下に接ぎ直す操作は木の上で行う。

entity の id はデータ木上の到達経路（`categories`、`categories.tasks`）で、`from:` はこれで entity を名指す。

レコード一件の型（ObjectType）はこれと別の id を持つ（`data_catalog.py` の `_item_type_id`）。ビューの派生 entity が、元の entity と違う id を持ちながら同じ型のレコードを並べるため。

派生 entity は元のレコード型を `origin_item_type` として引き継ぎ、`generate` はそれでレコードが内蔵の prose / blob 由来かを見分ける。レコードを組み替えたビュー（flatten、join）は元の型の実例ではなくなるので、引き継がない。

どちらの id もスキーマ上の位置を示す型レベルの識別子で、データ木上の個々のレコードの住所であるアンカーパス（`docs/reference/template.md` の Anchor paths）とは別物。アンカーパスの組み立てに、これらの id は登場しない。
