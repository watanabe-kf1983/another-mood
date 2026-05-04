# Template

**テンプレート**は、ビューを Markdown ドキュメントに変換する表現層。[Jinja2](https://jinja.palletsprojects.com/) をベースに、ファイル出力を司る `{% mood_view %}` タグを独自に拡張している。

テンプレートは `{project}/definition/templates/` 配下に `.md` 拡張子で置く。拡張子を `.md` にするのは、エディタのシンタックスハイライトに乗せて本文の編集体験を確保するため（テンプレート記法と Markdown 本文が混在するので、プレーンテキストとして扱うと視覚的に区別しづらい）。

## エントリポイント: `index.md`

`definition/templates/index.md` がルートテンプレート。テンプレートエンジンはここから評価を始める。ドキュメント全体の TOC（目次）を `index.md` に書き、サブページは `{% mood_view %}` で呼び出す構成にする。

```jinja2
{# templates/index.md #}
# 商品カタログ

## 商品一覧

{%- for product in products %}
- [{{ product.name }}](product-detail/{{ product.id }}.md)
{%- endfor %}

{%- for product in products -%}
{% mood_view "product-detail" with product %}
{%- endfor %}
```

## テンプレートへのデータ入力

テンプレートからは、[Schema](schema.md) で宣言したエンティティのデータと、[Query](query.md) で定義したビューを **同じ名前空間** で参照できる。

- エンティティ: schema.yaml の `properties` のキー
- クエリビュー: `definition/queries/` 配下のファイル内トップレベルキー
- 散文ビュー (`prose`): `contents/` 配下の Markdown ファイルから自動生成（[Schema — 内蔵スキーマ: 散文](schema.md#内蔵スキーマ-散文-prose) 参照）

```jinja2
{# products は構造化データのエンティティ、bestsellers はクエリビュー #}
{% for product in products %}
  ...
{% endfor %}

{% for entry in bestsellers %}
  ...
{% endfor %}
```

## Jinja2 拡張: `{% mood_view %}`

`{% mood_view %}` はサブテンプレートをレンダリングして **別ファイルに書き出す** 独自タグ。

```jinja2
{% mood_view "NAME" with DATA %}
```

| 部分 | 説明 |
|---|---|
| `NAME` | サブテンプレートのベース名（拡張子 `.md` を除いた名前を文字列で） |
| `DATA` | サブテンプレートに渡すデータ（マップオブジェクト） |

`DATA` がマップでない場合はエラー。

### 出力先の自動決定

`DATA` に `id` フィールドがあるかどうかで出力先パスが決まる。

| `DATA` | 出力先 |
|---|---|
| `{ id: "foo", ... }` を含む | `{outDir}/NAME/foo.md` |
| `id` フィールドなし | `{outDir}/NAME.md` |

### タグの戻り値

`{% mood_view %}` タグ自体は **空文字列を返す**。出力ファイルは副作用として書き出されるので、親テンプレート内で `{% mood_view %}` を置いた位置には何も現れない（空白のみ）。

親ページからサブページへのリンクを張りたい場合は、`{% mood_view %}` の外側に Markdown のリンク記法を別途書く:

```jinja2
{%- for product in products %}
- [{{ product.name }}](product-detail/{{ product.id }}.md)
{%- endfor %}

{%- for product in products -%}
{% mood_view "product-detail" with product %}
{%- endfor %}
```

### サブテンプレート側

サブテンプレート内では、`with` で渡したマップのフィールドがトップレベル変数として参照できる。

```jinja2
{# templates/product-detail.md #}
# {{ name }}

{{ description }}

| 項目 | 値 |
|------|-----|
{% for spec in specs -%}
| {{ spec.label }} | {{ spec.value }} |
{% endfor %}
```

### `inline` オプション

`with DATA` の後ろに `inline` を付けると、サブテンプレートの結果を **別ファイルに書き出さず**、そのまま呼び出し位置に展開する（`{% include %}` に近い動作）。

```jinja2
{% mood_view "NAME" with DATA inline %}
```

`{% mood_view %}` のデフォルト挙動（別ファイル出力）では複数のセクションが別々のページに散ってしまうケースで、それらを 1 ページに集約したいときに使う。

## Undefined アクセスの扱い

テンプレート内で未定義の変数・属性にアクセスしてもエラーにはならず、空文字列としてレンダリングされる。属性のチェインアクセス（例: `spec.metadata.title`）も、途中のキーが存在しなくても空文字列になる。

したがって optional な属性を参照する際、`if metadata is defined` のようなガードは不要:

```jinja2
{# metadata や metadata.title が存在しなくても安全 #}
| {{ spec.id }} | {{ spec.metadata.title }} |
```

スペルミスのときも同じくエラーにならず黙って空になる点に注意。書きながら `__table_view/` でデータの実体を、`__meta_query/` でクエリの結果形を確認しながら進める。
