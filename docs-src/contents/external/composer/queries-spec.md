# Queries Specification

クエリ定義の仕様。YAML DSL による正規化済みデータの整形・射影・結合を定義する。

## ファイル構成

`queriesDir`（デフォルト: `definition/queries/`）配下に YAML ファイルとして配置する。

```
{queriesDir}/
  erds.yaml            # entities を category で group した view
  screen-details.yaml  # screens を加工した view
```

## データソース

クエリは `normalizedContentsDir` の正規化済みデータに対して評価される。`from:` にはデータソース名を指定する。データソース名は `normalizedContentsDir` 内のファイル名（拡張子なし）のトップレベルキーに対応する。

### 自動パススルー

正規化済みデータは自動的に views にコピーされる（パススルー）。`contentsDir` に配置したデータは、クエリを書かなくてもテンプレートから参照可能。クエリは追加の view（group、join 等）を定義する場合にのみ記述する。

### 同名禁止

クエリ名と正規化済みデータ名（テーブル名）の重複は禁止する（エラー）。クエリの `from:` は常に正規化済みデータ（テーブル）を指すため、同名を許すと循環参照が生じる。加工が必要な場合はクエリに別名を付ける。

## YAML DSL

### 構造

1 つの YAML ファイルに複数のクエリを定義できる。トップレベルキーがクエリ名（= ビュー名）になる。

```yaml
# queries/erds.yaml
erds:
  from: entities
  grouped:
    by: category
  select:
    - item: category
      as: id
    - item: category
    - item: entities
```

### 句

| 句 | 必須 | 説明 |
|---|---|---|
| `from` | 必須 | データソース名 |
| `grouped` | 任意 | グループ化 |
| `select` | 任意 | 出力フィールドの指定。省略時は空オブジェクトの配列 |

将来の拡張候補: `where`, `sort`, `join`

### from

データソースとなる正規化済みデータの名前を指定する。

```yaml
from: entities    # normalizedContentsDir 内の entities をソースとする
```

### grouped

オブジェクト配列を指定フィールドでグループ化する。結果は配列で、各要素はグループキーの値とグループ内の要素配列を持つ。

```yaml
grouped:
  by: category          # グループ化するフィールド
  as: entities          # グループ内配列の名前（省略時は from の値）
```

**`by`** — グループ化のキーとなるフィールド名。

**`as`** — グループ内の要素配列に付ける名前。省略時は `from` で指定したデータソース名が使われる。

#### 出力形式

`from: entities` + `grouped: { by: category }` の場合:

```yaml
# 入力: entities
- { id: user, category: user-management, ... }
- { id: role, category: user-management, ... }
- { id: order, category: order-management, ... }

# 出力（select 適用前）
- category: user-management
  entities:                          # as 省略のため from の値 "entities"
    - { id: user, category: user-management, ... }
    - { id: role, category: user-management, ... }
- category: order-management
  entities:
    - { id: order, category: order-management, ... }
```

### select

出力に含めるフィールドを列挙する。`select` を省略した場合、空オブジェクトの配列が出力される。

各要素は以下のいずれか:

**`item`** — 出力に含めるフィールド名。

**`as`** — 出力時のフィールド名。省略時は `item` の値がそのまま使われる。

```yaml
select:
  - item: category
    as: id              # category の値を id という名前で出力
  - item: category      # category をそのまま出力
  - item: entities      # grouped.as の配列を出力
```

`select` に列挙しないフィールドは出力に含まれない。`grouped` で生成されるキーフィールドやグループ配列も、`select` に明示しなければ出力されない。

## 例: example-project

### データソース

```yaml
# contents/entities.yaml
entities:
  - id: user
    name: ユーザー
    category: user-management
    fields: [...]
  - id: role
    name: ロール
    category: user-management
    fields: [...]
  - id: order
    name: 注文
    category: order-management
    fields: [...]
```

### クエリ定義

```yaml
# queries/erds.yaml
erds:
  from: entities
  grouped:
    by: category
  select:
    - item: category
      as: id
    - item: category
    - item: entities
```

### 出力

```yaml
# views/erds.yaml（Composer が生成）
erds:
  - id: user-management
    category: user-management
    entities:
      - { id: user, name: ユーザー, category: user-management, fields: [...] }
      - { id: role, name: ロール, category: user-management, fields: [...] }
  - id: order-management
    category: order-management
    entities:
      - { id: order, name: 注文, category: order-management, fields: [...] }
```

テンプレートでは `entities` を直接イテレートできる:

```jinja2
{# templates/erd.md #}
{% for entity in entities %}
### {{ entity.name }}
{{ entity.description }}
{% endfor %}
```

## 出力

views は `viewsDir` に YAML ファイルとして書き出される。自動パススルー分と、クエリ評価結果の両方が含まれる。

```
{viewsDir}/
  entities.yaml       # 自動パススルー（normalized からコピー）
  relations.yaml      # 自動パススルー
  erds.yaml           # {queriesDir}/erds.yaml の評価結果
```
