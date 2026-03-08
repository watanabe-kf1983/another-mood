# Reports 層再設計

2025-03-08 の設計議論を元にした、toc 層とテンプレート層の再設計案。

## 背景

現行設計には以下の課題がある：

1. **toc の責務が曖昧**: 「ドキュメント単位の導出」と言いつつ `permalink` や `sectionId` というページルーティングの情報を持つ
2. **テンプレートのフロントマターとの責務重複**: ページ定義が toc と template の両方に分散（permalink が二箇所に出現）
3. **11ty への不要な依存**: pagination・フロントマター処理のためだけに 11ty を使っているが、テンプレートレンダリング自体は LiquidJS で行っている
4. **テンプレートがグローバルなコンテキストに依存**: 各テンプレートが `source` ルートオブジェクトから必要なデータを自力で掘り出している

## 新設計

### アーキテクチャ概要

```
source → reports → template（root.md + パーシャル群）
                 → paging（クラス → ファイルパスのマッピング）
```

- **source**: ドメインの真実（正規化されたデータ）
- **reports**: 整形・射影（source データを加工してツリー構造を作る）
- **template**: 表現（root テンプレートから `{% section %}` でパーシャルに委譲）
- **paging**: ファイル分割戦略（クラスごとにファイルパスを定義）

旧設計の toc 層と pages 層は廃止。目次（ToC）はドキュメントの責務ではなく出力ツール（Hugo, pandoc 等）の責務。

### reports: 整形・射影

reports は source データを整形・射影し、テンプレートに渡すツリー構造を作る。

```yaml
# reports/erd.yaml.liquid
erd:
  {% assign categories = source.entities | map: "category" | uniq %}
  {% for cat in categories %}
  - key: "{{ cat }}"
    title: "{{ cat }} の ER図"
    entity:
      {% assign ents = source.entities | where: "category", cat %}
      {% for e in ents %}
      - key: "{{ e.id }}"
        title: "{{ e.name }}"
        field:
          {% for f in e.fields %}
          - name: "{{ f.name }}"
            type: "{{ f.type }}"
          {% endfor %}
      {% endfor %}
    relation:
      {% assign rels = source.relations | where: "category", cat %}
      {% for r in rels %}
      - from: "{{ r.from }}"
        to: "{{ r.to }}"
        cardinality: "{{ r.cardinality }}"
      {% endfor %}
  {% endfor %}
```

#### key 属性

- `key`: 機械的な識別子。英数字・ハイフン・アンダースコアのみ
- `title`: 人間向けの表示名（日本語OK）
- `key` はクラス内でユニーク
- `key` を持つオブジェクトは自動的にフラットアンカーマップに登録される（リンク可能になる）

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

### template: 表現

#### root テンプレート

ユーザが必ず書くエントリポイント。ドキュメント全体の構成を定義する：

```liquid
{# templates/root.md.liquid #}
# システム要件定義書

{% section "erd" for reports.erd %}
{% section "screen" for reports.screen %}
{% section "usecase" for reports.usecase %}
```

読者や目的が異なる場合は root テンプレートを分ける（社内向け、顧客向け等）。

#### `{% section %}` カスタムタグ

`{% section %}` は描画をパーシャルテンプレートに委譲する。paging 設定に応じて振る舞いが変わる：

- 対象クラスが paging の分割単位 → 別ファイルに出力し、親にはリンクを残す
- 分割単位でない → インライン展開（通常の `{% render %}` と同等）

```liquid
{# templates/erd.md.liquid #}
# {{ entry.title }}

{% section "entity-detail" for entry.entity %}
{% section "mermaid-er" with entry.relation %}
```

テンプレート作者は paging を意識しない。同じテンプレートが Web 用（分割）でも PDF 用（全部インライン）でもそのまま動く。

`{% section %}` は anchor の有無に関係なく使える。anchor と section は直交する概念：
- anchor（`key` 属性）: リンク可能かどうか
- section: 描画を委譲するかどうか

#### パーシャルテンプレート

パーシャル単位で出力フォーマットが決まり、拡張子でエスケープモードを判定する：

```
templates/
  root.md.liquid             → markdown エスケープ
  erd.md.liquid              → markdown エスケープ
  entity-detail.md.liquid    → markdown エスケープ
  mermaid-er.mermaid.liquid  → mermaid エスケープ
reports/
  erd.yaml.liquid            → yaml エスケープ
```

### paging: ファイル分割戦略

クラスとファイルパステンプレートのマッピング。プロファイルとして複数定義し、用途に応じて切り替える：

```yaml
# paging/web.yaml
pages:
  - class: erd
    path: "erd/{{ key }}.md"
  - class: erd.entity
    path: "erd/{{ key }}/entities.md"
```

```yaml
# paging/pdf.yaml
pages:
  - class: erd
    path: "all.md"
```

paging 設定に列挙されたクラスが分割単位。列挙されていないクラスの `{% section %}` はインライン展開される。

paging に列挙できるのは `key` を持つクラスに限られる（ファイル名生成に `key` が必要なため）。

### フラットアンカーマップ

エンジンがレポートツリーを再帰的に走査し、`key` を持つオブジェクトからフラットマップを自動構築する。

構築手順：

1. ツリー走査 → `key` 持ちオブジェクトの ID（`{class}.{key}`）を収集
2. paging 設定を適用 → 各アンカーが属するページの href を確定
   - paging に該当するクラス → そのページの href
   - 該当しないクラス → 親を辿って最も近い「ページになるアンカー」の href + `#id`
3. テンプレートエンジン起動前にマップ構築を完了させる

テンプレートからは `link_md` フィルタ経由でアクセス。Markdown 内からは `toc:id` 記法でアクセス。

### リンク解決

#### テンプレート内（link_md フィルタ）

```liquid
{{ "erd.entity.user" | link_md }}
```

→ `[ユーザー](../erd/user-management.md#erd.entity.user)` のような相対リンクを生成。
（title をマップに持たせるかどうかは実装時に判断。最低限は href のみで動く。）

#### Markdown source 内（toc:id 記法）

```markdown
ユーザーの詳細は[ユーザー](toc:erd.entity.user)を参照。
```

エンジンが `toc:erd.entity.user` をフラットマップから解決し、適切な相対パスに置換する。

## 処理フロー

```
1. source/*.yaml 読み込み → source オブジェクト構築
2. reports/*.yaml.liquid 評価（source を渡す）→ レポートツリー構造を得る
3. ツリー走査 → key 持ちオブジェクトからフラットアンカーマップ構築（ID のみ）
4. paging 設定 × フラットマップ → 各アンカーの href を確定
5. root テンプレートからレンダリング開始
   - {% section %} が paging を参照し、分割 or インライン判定
   - link_md フィルタがフラットマップを参照しリンク生成
6. Markdown 内の toc:id リンクをフラットマップから解決
7. ファイル書き出し
```

## 11ty 除去

現在 11ty が担っている機能は全て自前で代替する：

| 11ty の機能 | 代替手段 |
|---|---|
| フロントマター解析 | 不要（テンプレートからフロントマター削除） |
| pagination | paging 設定 + `{% section %}` タグ |
| permalink 解決 | paging 設定のパステンプレート |
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
- [ ] example-project でフラットアンカーマップの href 解決を具体例で検証する
  - 特に paging 設定にないクラスの親辿りロジック

## 将来の検討事項

### Python 移行

TypeScript から Python への移行は選択肢として残す。移行する場合：

- テンプレートエンジン: LiquidJS → Jinja2（フィルタがより豊富、マクロが使える）
- 11ty 抜きの TypeScript 実装を参照実装として使う
- example-project のフィクスチャとテストの期待値は言語非依存で流用可能

判断材料：

- メリット: Jinja2 の表現力、コード量削減
- デメリット: 移行コスト、npx の手軽さ喪失（uvx で代替可能）
