# ToC 再設計

2025-03-08 の設計議論を元にした、toc 層とテンプレート層の再設計案。

## 背景

現行設計には以下の課題がある：

1. **toc の責務が曖昧**: 「ドキュメント単位の導出」と言いつつ `permalink` や `sectionId` というページルーティングの情報を持つ
2. **テンプレートのフロントマターとの責務重複**: ページ定義が toc と template の両方に分散（permalink が二箇所に出現）
3. **11ty への不要な依存**: pagination・フロントマター処理のためだけに 11ty を使っているが、テンプレートレンダリング自体は LiquidJS で行っている
4. **テンプレートがグローバルなコンテキストオブジェクトに依存**: 各テンプレートが `source` ルートオブジェクトから必要なデータを自力で掘り出している

## 新設計

### 層の責務

| 層 | ファイル | 責務 |
|---|---|---|
| source | `source/*.yaml` | ドメインの真実（正規化されたデータ） |
| toc | `toc/*.yaml.liquid` | リンクレジストリ（ドキュメント単位 + リンク先情報） |
| pages | `pages.yaml.liquid` | ページ定義（ルーティング + テンプレート指定） |
| template | `templates/*.md` | 表現（渡されたコンテキストをどう描くか） |

### toc: リンクレジストリ

toc は **リンクレジストリ** として再定義する。ドキュメント単位を定義し、相互リンクの基盤を提供する。

#### データ構造

toc エントリは以下の属性を持つ：

| 属性 | 必須 | 説明 |
|------|------|------|
| `name` | ○ | クラス内でユニークな名称 |
| `title` | ○ | 表示用タイトル |
| `children` | - | 子エントリ（ラッパーキーがクラス名） |

ラッパーキー（YAML のキー名）がそのままクラス名になる：

```yaml
# toc/erds.yaml.liquid
erds:                          # ← class: erd
  {% assign categories = source.entities | map: "category" | uniq %}
  {% for cat in categories %}
  - name: {{ cat }}
    title: {{ cat }} の ER図
    entities:                  # ← class: entity（children のラッパーキー）
      {% assign ents = source.entities | where: "category", cat %}
      {% for e in ents %}
      - name: {{ e.id }}
        title: {{ e.name }}
      {% endfor %}
  {% endfor %}
```

#### ID 体系

グローバルにユニークな ID はエンジンが自動生成する：

- ID = `{class}.{name}`（例: `erd.user-management`, `entity.user`）
- ラッパーキーの複数形からクラス名（単数形）を導出
- `name` はユーザが命名、クラス内でユニーク

同じ `name` でも異なるクラスなら共存できる：

| id | class | name | title |
|---|---|---|---|
| `erd.user-management` | erd | user-management | ユーザー管理の ER図 |
| `entity.user` | entity | user | ユーザー |
| `screen.user` | screen | user | ユーザー画面 |

#### フラットインデックス

エンジンがツリーを再帰的に走査し、フラットインデックスを自動構築する。
テンプレートやMarkdownから相互リンクに使用する。

子要素の `href` は親の `href` + `#id` から自動導出される：

| id | href（自動生成） |
|---|---|
| `erd.user-management` | `erds/user-management.md` |
| `entity.user` | `erds/user-management.md#entity.user` |
| `entity.role` | `erds/user-management.md#entity.role` |

### pages: ページ定義

pages はフラットな toc インデックスから特定のクラスをフィルタし、
物理的なページ（ファイル出力）を定義する：

```yaml
# pages.yaml.liquid
{% assign erds = toc | where: "class", "erd" %}
{% for entry in erds %}
- id: {{ entry.id }}
  href: erds/{{ entry.name }}.md
  template: erd
{% endfor %}
```

- ページ定義のあるエントリ → 独立したファイルとして出力
- ページ定義のないエントリ → 親の href + `#id` がリンク先（セクション扱い）

pages が生成した `href` はフラットインデックスに書き戻される。

### template: 表現

テンプレートは **フロントマターを持たない**。エンジンから `{ source, toc, entry }` を受け取り、描画するだけ：

```liquid
{# templates/erd.md — フロントマターなし #}
# {{ entry.title }}

{% assign entities = source.entities | where: "category", entry.name %}
{% for entity in entities %}
### {{ entity.name }}
...
{% endfor %}
```

将来的に `{% render %}` を使ったパーシャル分離も可能：

```liquid
{% assign entities = source.entities | where: "category", entry.name %}
{% render "entity-fields-table" for entities %}
```

### リンク解決

3つのチャネルで統一的にリンクを解決する：

#### 1. テンプレート内（find フィルタ）

```liquid
{% assign target = toc | find: "entity.user" %}
[{{ target.title }}]({{ target.href | relativeFrom: entry.href }})
```

#### 2. Markdown source 内（toc:id 記法）

```markdown
ユーザーの詳細は[ユーザー](toc:entity.user)を参照。
```

エンジンが `toc:entity.user` をフラットインデックスから解決し、適切な相対パスに置換する。

#### 3. 目次ページ（ツリー構造をそのまま描画）

```liquid
{% for entry in toc.erds %}
- [{{ entry.title }}]({{ entry.href | relativeFrom: current.href }})
  {% for child in entry.children %}
  - [{{ child.title }}]({{ child.href | relativeFrom: current.href }})
  {% endfor %}
{% endfor %}
```

## 処理フロー

```
1. source/*.yaml 読み込み → source オブジェクト構築
2. toc/*.yaml.liquid 評価（source を渡す）→ ツリー構造を得る
3. ツリー → フラットインデックス構築（id, name, class, title）
4. pages.yaml.liquid 評価（フラットインデックスを渡す）→ ページ定義
5. ページ定義の href をフラットインデックスに書き戻し
6. ページ定義のないエントリは 親の href + #id で href を補完
7. 各ページの class → templates/{class}.md を解決
8. { source, toc, entry } をコンテキストとしてレンダリング
9. Markdown 内の toc:id リンクをフラットインデックスから解決
10. entry.href にファイル書き出し
```

## 11ty 除去

現在 11ty が担っている機能は全て自前で代替する：

| 11ty の機能 | 代替手段 |
|---|---|
| フロントマター解析 | 不要（テンプレートからフロントマター削除） |
| pagination | pages.yaml.liquid + エンジンの for ループ |
| permalink 解決 | pages のページ定義 + フラットインデックス |
| ファイル書き出し | fs.writeFileSync |
| テンプレートレンダリング | LiquidJS（既に自前） |

## 将来の検討事項

### Python 移行

TypeScript から Python への移行は選択肢として残す。移行する場合：

- テンプレートエンジン: LiquidJS → Jinja2（フィルタがより豊富、マクロが使える）
- 11ty 抜きの TypeScript 実装を参照実装として使う
- example-project のフィクスチャとテストの期待値は言語非依存で流用可能

判断材料：
- メリット: Jinja2 の表現力、コード量削減
- デメリット: 移行コスト、npx の手軽さ喪失（uvx で代替可能）

### パーシャルテンプレート

`{% render %}` / `{% include %}` によるテンプレート分離。
「整形・射影」と「表現」を分離し、再利用可能な表現パーツを作る：

```liquid
{# templates/partials/entity-fields-table.md #}
### {{ name }}
| フィールド | 型 | 備考 |
{% for field in fields %}
| {{ field.name }} | {{ field.type }} | ... |
{% endfor %}
```

toc 再設計と 11ty 除去の後に、必要に応じて導入する。
