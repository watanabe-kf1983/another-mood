# Reports 層再設計

2025-03-08 の設計議論を元にした、toc 層とテンプレート層の再設計案。

## 背景

現行設計には以下の課題がある：

1. **toc の責務が曖昧**: 「ドキュメント単位の導出」と言いつつ `permalink` や `sectionId` というページルーティングの情報を持つ
2. **テンプレートのフロントマターとの責務重複**: ページ定義が toc と template の両方に分散（permalink が二箇所に出現）
3. **11ty への不要な依存**: pagination・フロントマター処理のためだけに 11ty を使っているが、テンプレートレンダリング自体は LiquidJS で行っている
4. **テンプレートがグローバルなコンテキストに依存**: 各テンプレートが `source` ルートオブジェクトから必要なデータを自力で掘り出している

## 新設計

### 層の責務

| 層 | ファイル | 責務 |
|---|---|---|
| source | `source/*.yaml` | ドメインの真実（正規化されたデータ） |
| reports | `reports/*.yaml.liquid` | 整形・射影 + アンカー定義（相互リンクの基盤） |
| template | `templates/*.md` | 表現（渡されたコンテキストをどう描くか） |

旧設計の toc 層と pages 層を **reports 層** に統合。reports がデータの整形・射影とアンカー（リンクポイント）定義の両方を担う。

### reports: 整形・射影 + アンカー

reports は source データを **整形・射影** し、テンプレートに渡す形に加工する。
同時に、**アンカー** を定義して相互リンクの基盤を提供する。

#### データ構造

```yaml
# reports/erd.yaml.liquid
erd:
  {% assign categories = source.entities | map: "category" | uniq %}
  {% for cat in categories %}
  - key: {{ cat }}
    title: {{ cat }} の ER図
    anchor: true
    entity:
      {% assign ents = source.entities | where: "category", cat %}
      {% for e in ents %}
      - key: {{ e.id }}
        title: {{ e.name }}
        anchor: true
        field:
          {% for f in e.fields %}
          - name: {{ f.name }}
            type: {{ f.type }}
          {% endfor %}
      {% endfor %}
    relation:
      {% assign rels = source.relations | where: "category", cat %}
      {% for r in rels %}
      - from: {{ r.from }}
        to: {{ r.to }}
        cardinality: "{{ r.cardinality }}"
      {% endfor %}
  {% endfor %}
```

#### key 属性

- `key`: 機械的な識別子。英数字・ハイフン・アンダースコアのみ
- `title`: 人間向けの表示名（日本語OK）
- `key` はクラス内でユニーク

#### anchor 属性

`anchor` はエントリをリンク可能にする（フラットインデックスに登録する）指定：

| 記法 | 意味 |
|------|------|
| `anchor: true` | 親オブジェクトの `key` と `title` を使用 |
| `anchor: { key: xxx, title: yyy }` | key / title をオーバーライド |
| （anchor なし） | リンク不可（フラットインデックスに登録しない） |

#### ID 体系

グローバルにユニークな ID はエンジンが自動生成する：

- class = ラッパーキーのドット区切りパス（例: `erd`, `erd.entity`）
- ID = `{class}.{key}`（例: `erd.user-management`, `erd.entity.user`）
- ラッパーキーは **単数形** で記述する

同じ `key` でも異なるクラスなら共存できる：

| id | class | key | title |
|---|---|---|---|
| `erd.user-management` | erd | user-management | ユーザー管理の ER図 |
| `erd.entity.user` | erd.entity | user | ユーザー |
| `screen.user` | screen | user | ユーザー画面 |

#### ページ vs セクション

pages 層は不要。アンカーのネスト関係から自動判定する：

- **ページ**: 親にアンカーを持たないアンカー（トップレベルアンカー）
  - 独立したファイルとして出力
  - href = `{class}/{key}.md`
- **セクション**: 親にアンカーを持つアンカー（ネストされたアンカー）
  - 親ページ内のセクションとして出力
  - href = `{parent_href}#{id}`

例：

| id | 種別 | href（自動生成） |
|---|---|---|
| `erd.user-management` | ページ | `erd/user-management.md` |
| `erd.entity.user` | セクション | `erd/user-management.md#erd.entity.user` |
| `erd.entity.role` | セクション | `erd/user-management.md#erd.entity.role` |

#### フラットインデックス（_anchors）

エンジンがレポートツリーを再帰的に走査し、`anchor` 付きエントリからフラットインデックスを自動構築する。

- 内部実装名: `_anchors`（ユーザに露出しない）
- テンプレートからは `link_md` フィルタ経由でアクセス
- Markdown 内からは `toc:id` 記法でアクセス

### template: 表現

テンプレートは **フロントマターを持たない**。エンジンから `entry` を受け取り、描画するだけ：

```liquid
{# templates/erd.md — フロントマターなし #}
# {{ entry.title }}

{% render "entity-detail" for entry.entity %}
{% render "mermaid-er-relations" with entry.relations %}
```

テンプレート解決: class → テンプレートファイル名（例: `erd` → `templates/erd.md`）

#### パーシャルテンプレート

`{% render %}` / `{% include %}` によるテンプレート分離。
再利用可能な表現パーツを作る：

```liquid
{# templates/entity-detail.md #}
## {{ key }}（{{ title }}）

| フィールド | 型 |
|--------|-----|
{% for f in field %}
| {{ f.name }} | {{ f.type }} |
{% endfor %}
```

### リンク解決

2つのチャネルで統一的にリンクを解決する：

#### 1. テンプレート内（link_md フィルタ）

```liquid
{{ "erd.entity.user" | link_md }}
```

→ `[ユーザー](../erd/user-management.md#erd.entity.user)` のような相対リンクを生成。

#### 2. Markdown source 内（toc:id 記法）

```markdown
ユーザーの詳細は[ユーザー](toc:erd.entity.user)を参照。
```

エンジンが `toc:erd.entity.user` をフラットインデックスから解決し、適切な相対パスに置換する。

## 処理フロー

```
1. source/*.yaml 読み込み → source オブジェクト構築
2. reports/*.yaml.liquid 評価（source を渡す）→ レポートツリー構造を得る
3. ツリー走査 → anchor 付きエントリからフラットインデックス（_anchors）構築
4. トップレベルアンカー → ページ（href = {class}/{key}.md）
5. ネストアンカー → セクション（href = parent_href + #id）
6. 各ページの class → templates/{class}.md を解決
7. { entry } をコンテキストとしてレンダリング（_anchors は link_md フィルタ内部で参照）
8. Markdown 内の toc:id リンクをフラットインデックスから解決
9. entry の href にファイル書き出し
```

## 11ty 除去

現在 11ty が担っている機能は全て自前で代替する：

| 11ty の機能 | 代替手段 |
|---|---|
| フロントマター解析 | 不要（テンプレートからフロントマター削除） |
| pagination | reports のツリー構造 + エンジンの for ループ |
| permalink 解決 | アンカーのネスト関係から自動導出 |
| ファイル書き出し | fs.writeFileSync |
| テンプレートレンダリング | LiquidJS（既に自前） |

## TODO

- [ ] テンプレートエンジンのエスケープ仕様を確認する（LiquidJS / Jinja2）
  - 出力フォーマットごとにエスケープモードを切り替える必要がある
  - YAML: `"` と `\` のエスケープ（ノルウェー問題対策、テンプレート側で `"{{ value }}"` とクォートを書く前提）
  - Markdown: `|`, `#`, `*` 等の文脈依存エスケープ
  - Mermaid: `[`, `{`, `"` 等の記法衝突
  - パーシャル単位でエスケープモードを切り替え（拡張子で判定: `.md.liquid`, `.mermaid.liquid`, `.yaml.liquid`）
  - クォートなし `{{ }}` を YAML テンプレートで検出するリンター/警告も検討

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

`{% render %}` によるテンプレート分離は reports 再設計と同時に導入可能。
LiquidJS の `{% render %}` は Jinja2 の `{% include %}` / `{% import %}` に相当する。
