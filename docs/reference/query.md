# Query

**クエリ**は、構造化データを参照しやすい形に加工して **ビュー** を定義する YAML ファイル。グループ化・フィールドの射影などを書ける。

クエリは `{project}/definition/queries/` 配下の YAML ファイル（`.yaml` / `.yml`、大小文字不問）に書く。ファイル数や分割の仕方・サブディレクトリ配置は自由で、ビルド時にまとめて評価される。1 ファイルに複数のクエリを書いてもよい — ファイルのトップレベルキーがビュー名になる。

## クエリの基本構造

ビュー定義の構造:

```yaml
# queries/by_role.yaml
by_role:                     # ← ファイルのトップレベルキーがビュー名
  from: members              # 必須
  grouped:                   # 任意
    by: role
  select:                    # 任意
    - item: role
      as: id
    - item: role
    - item: members
```

| 句 | 必須 | 役割 |
|---|---|---|
| `from` | 必須 | 元データ（何を材料にするか） |
| `grouped` | 任意 | レコードのグループ化 |
| `select` | 任意 | 出力フィールドの射影。省略時は空オブジェクトの配列 |

評価順は `from` → `grouped` → `select`。

## 自動パススルー

[Schema](schema.md) で宣言したエンティティのデータは、クエリを書かなくてもテンプレートからエンティティ名でそのまま参照できる（自動パススルー）。クエリは追加のビュー（グループ化、射影など）を定義する場合にのみ書く。

## from

元データとなるエンティティを指定する。エンティティ名は schema.yaml の `properties` のキー（= コンテンツファイルのトップレベルキー）と一致する。

```yaml
from: members    # エンティティ members を元データとする
```

### 子エンティティのドット記法

`from` にはドット記法でネストされた子エンティティを指定できる。親から取り外し、フラットな配列として取り出す。

```yaml
from: categories.tasks   # categories 配下の tasks をフラットに展開
```

任意の深さまで連結可能:

```yaml
from: a.b.c.d   # a → b → c → d の順に段階的にフラット化
```

各セグメントの値は **オブジェクトまたはオブジェクト配列**（任意段数のネスト配列で包まれていても可）。単一オブジェクトは 1 要素として、配列は深さに関わらず平坦化・連結される。

## grouped

オブジェクト配列を指定フィールドでグループ化する。結果は配列で、各要素はグループキーの値とグループ内の要素配列を持つ。

```yaml
grouped:
  by: role               # グループ化のキー
  as: members            # グループ内配列の名前（省略時は from の末尾セグメント）
```

| キー | 必須 | 役割 |
|---|---|---|
| `by` | 必須 | グループ化のキーとなるフィールド名 |
| `as` | 任意 | グループ内の要素配列に付ける名前。省略時は `from` の末尾セグメント（ドット記法なら最後のキー） |

グループの出現順は元データの出現順に従う（最初に現れたキーの順）。グループ内のレコードは元データの形そのまま（グループキーのフィールドも保持される）。

### 出力形式

`from: members` + `grouped: { by: role }` の場合、入力:

```yaml
members:
  - { id: alice, name: Alice, role: engineer }
  - { id: bob,   name: Bob,   role: engineer }
  - { id: carol, name: Carol, role: designer }
```

に対する `grouped` 適用後（`select` 適用前）の中間結果:

```yaml
- role: engineer
  members:                             # as 省略のため from の末尾 "members"
    - { id: alice, name: Alice, role: engineer }
    - { id: bob,   name: Bob,   role: engineer }
- role: designer
  members:
    - { id: carol, name: Carol, role: designer }
```

## select

出力に含めるフィールドを列挙する。省略した場合は空オブジェクトの配列が出力される。

```yaml
select:
  - item: role
    as: id              # role の値を id という名前で出力
  - item: role          # role をそのまま出力
  - item: members       # grouped.as の配列を出力
```

| キー | 必須 | 役割 |
|---|---|---|
| `item` | 必須 | 入力レコードから取り出すフィールド名 |
| `as` | 任意 | 出力時のフィールド名。省略時は `item` の値がそのまま使われる |

`select` に列挙しないフィールドは出力に含まれない。`grouped` で生成されるキーフィールドやグループ配列も、`select` で明示しなければ出力されない。

## ビューの確認

各クエリの結果は `output/__meta_query/<query>.md` に自動生成されるメタページで確認できる。クエリを書きながら期待通りの結果になっているかを `mood watch` 上で見ながら進められる。

## query-schema 全文

クエリファイルの形を縛る内蔵スキーマ。本章の正典。

```yaml
title: QuerySchema
description: >-
  Meta-schema validating user-defined query files under queries_dir. Each
  top-level key names a query (= view) and maps to a definition with a
  required `from:` data source and optional `grouped:` / `select:` clauses.
  See docs/reference/query.md for the prose specification.

type: object
propertyNames:
  description: >-
    Query name pattern: starts with a Unicode letter or underscore,
    followed by Unicode letters, digits, or underscores.
  pattern: "^[\\p{L}_][\\p{L}\\p{N}_]*$"
additionalProperties:
  title: Query definition
  description: >-
    A single query (view) definition. `from:` selects the normalized data
    source; optional `grouped:` reshapes it into groups; optional `select:`
    projects the output fields. See docs/reference/query.md for semantics.
  type: object
  properties:
    from:
      title: Data source
      description: >-
        Name of the normalized data source to read from. Resolves to a
        top-level key of a YAML file under normalize_contents_dir (the
        key matches the file basename without extension). Dot notation
        (e.g. `categories.tasks`) flattens nested child entities into a
        single sequence.
      type: string
    grouped:
      title: Grouping clause
      description: >-
        Groups the source records by the value of one field. The output
        becomes an array of groups, each carrying the key value and an
        inner array of the group's members.
      type: object
      properties:
        by:
          title: Group key field
          description: Name of the field whose value defines each group.
          type: string
        as:
          title: Members array name
          description: >-
            Name given to the inner array of group members. Defaults to
            the value of `from:` when omitted.
          type: string
      required: [by]
      additionalProperties: false
    select:
      title: Output projection
      description: >-
        List of fields to include in the output. Fields not listed are
        omitted. When `select:` itself is omitted, each output record is
        an empty object.
      type: array
      items:
        title: Selected field
        description: >-
          One field to include in the output. `item:` names the source
          field; optional `as:` renames it in the output.
        type: object
        properties:
          item:
            title: Source field name
            description: Name of the field to read from each record.
            type: string
          as:
            title: Output field name
            description: >-
              Name to use in the output. Defaults to the value of `item:`
              when omitted.
            type: string
        required: [item]
        additionalProperties: false
  required: [from]
  additionalProperties: false
```
