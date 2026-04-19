# Query DSL

**クエリ**（query）は、正規化済みデータから派生した view を宣言する YAML DSL。既存のデータソースを材料に、グループ化やフィールドの射影を加えた結果を、新しい view として書き出す。

クエリは `{project}/definition/queries/` 配下の YAML ファイル（`.yaml` / `.yml`、大小文字不問）に書く。ファイルのトップレベルキーがクエリの名前（= 出力される view の名前）になる。ファイル数や分割の仕方・サブディレクトリ配置は自由で、ビルド時にまとめて評価される。

## クエリの基本構造

1 つの YAML ファイルに複数のクエリを書ける。トップレベルキーがクエリ名。

```yaml
# queries/erds.yaml
erds:
  from: entities           # 必須
  grouped:                 # 任意
    by: category
  select:                  # 任意
    - item: category
      as: id
    - item: category
    - item: entities
```

| 句 | 必須 | 役割 |
|---|---|---|
| `from` | 必須 | データソース（何を材料にするか） |
| `grouped` | 任意 | オブジェクト配列のグループ化 |
| `select` | 任意 | 出力フィールドの射影。省略時は空オブジェクトの配列 |

評価順は `from` → `grouped` → `select`。

## from

データソースとなる正規化済みデータ名を文字列で指定する。正規化済みデータ名は、スキーマ名（= `contents/` のトップレベルキー）と一致する。

```yaml
from: entities    # 正規化済みデータ entities をソースとする
```

### 子エンティティのドット記法

`from` にはドット記法で子エンティティを指定できる。ネストされた配列を親から取り外し、フラットな配列として取り出す。

```yaml
from: categories.tasks   # categories 配下の tasks を全部フラットに展開
```

任意の深さまで連結可能:

```yaml
from: a.b.c.d   # a → b → c → d の順に段階的にフラット化
```

各セグメントの値は**オブジェクトまたはオブジェクト配列**（任意段数のネスト配列で包まれていても可）。単一オブジェクトは 1 要素として扱い、配列は深さに関わらず平坦化・連結される。

## grouped

オブジェクト配列を指定フィールドでグループ化する。結果は配列で、各要素はグループキーの値とグループ内の要素配列を持つ。

```yaml
grouped:
  by: category          # グループ化のキー
  as: entities          # グループ内配列の名前（省略時は from の末尾セグメント）
```

| キー | 必須 | 役割 |
|---|---|---|
| `by` | 必須 | グループ化のキーとなるフィールド名 |
| `as` | 任意 | グループ内の要素配列に付ける名前。省略時は `from` の末尾セグメント（ドット記法なら最後のキー） |

グループの出現順は元データの出現順に従う（最初に現れたキーの順）。

### 出力形式

`from: entities` + `grouped: { by: category }` の場合、入力:

```yaml
entities:
  - { id: user, category: user-management, ... }
  - { id: role, category: user-management, ... }
  - { id: order, category: order-management, ... }
```

に対する `grouped` 適用後（`select` 適用前）の中間結果:

```yaml
- category: user-management
  entities:                          # as 省略のため from の末尾 "entities"
    - { id: user, category: user-management, ... }
    - { id: role, category: user-management, ... }
- category: order-management
  entities:
    - { id: order, category: order-management, ... }
```

## select

出力に含めるフィールドを列挙する。

```yaml
select:
  - item: category
    as: id              # category の値を id という名前で出力
  - item: category      # category をそのまま出力
  - item: entities      # grouped.as の配列を出力
```

各要素は:

| キー | 必須 | 役割 |
|---|---|---|
| `item` | 必須 | 入力レコードから取り出すフィールド名 |
| `as` | 任意 | 出力時のフィールド名。省略時は `item` の値がそのまま使われる |

`select` に列挙しないフィールドは出力に含まれない。`grouped` で生成されるキーフィールドやグループ配列も、`select` で明示しなければ出力されない。

`select` を省略した場合は、各レコードから何も取り出さない（空オブジェクトの配列が出力される）。
