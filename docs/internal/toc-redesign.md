# Query Engine + テンプレート層 再設計

2025-03-08〜09 の設計議論を元にした、toc 層・テンプレート層の再設計。

旧タイトル「Reports 層再設計」から改題。

## 背景

### 旧設計の課題

1. **toc の責務が曖昧**: 「ドキュメント単位の導出」と言いつつ `permalink` や `sectionId` というページルーティングの情報を持つ
2. **テンプレートのフロントマターとの責務重複**: ページ定義が toc と template の両方に分散
3. **11ty への不要な依存**: pagination・フロントマター処理のためだけに 11ty を使用
4. **テンプレートがグローバルなコンテキストに依存**: 各テンプレートが `source` ルートオブジェクトから必要なデータを自力で掘り出している

### テンプレートエンジンによるデータ変換の限界（2025-03-09 の議論で明確化）

旧 reports 層（旧 toc 層）は LiquidJS / Jinja2 テンプレートで source データを整形していた：

```yaml
# 旧: reports/erd.yaml.liquid（テンプレートエンジンでデータ変換）
erd:
  {% assign categories = source.entities | map: "category" | uniq %}
  {% for cat in categories %}
  - key: "{{ cat }}"
    title: "{{ cat }} の ER図"
    entity:
      {% assign ents = source.entities | where: "category", cat %}
      ...
  {% endfor %}
```

これは本質的に SQL の SELECT / WHERE / DISTINCT / GROUP BY に相当する操作を、テキスト生成エンジンで行っている。問題点：

1. **データ→テキスト→データのラウンドトリップ**: source（オブジェクト）→ Liquid でテキスト生成 → YAML パース → オブジェクト。不要な変換が2回入る
2. **YAML エスケープ問題**: テキストとして YAML を生成するため、ノルウェー問題（`NO` が boolean 扱い）等のエスケープ問題が発生する
3. **型の劣化**: テキスト経由で整数・浮動小数の区別等が失われる可能性

### MS-Access アナロジー

source / queries / templates の三層構造は MS-Access の Table / Query / Form・Report に対応する：

| MS-Access | このアプリ | 役割 |
|---|---|---|
| Table | source/ | 正規化されたデータ |
| Query (View) | queries/ | データの整形・射影・結合の**定義** |
| Form / Report | templates/ | 表現・レイアウト |

Access の Query は SQL で書く。テンプレートエンジンで Query を書くのは、Excel のセルに SQL を文字列として組み立てるようなもの。Query にはクエリ言語を使うべき。

## 新設計

### アーキテクチャ概要

```
model/
  source/ + queries/  →  Validator APP  →  output/prepared/
presentation/
  templates/ + paging/ →  Generator APP  →  output/documents/
                          Renderer (Hugo) →  output/rendered/
```

- **source/**: ドメインの真実（正規化されたデータ）
- **queries/**: データの整形・射影・結合の定義（JSONata 式）
- **templates/**: 表現（root テンプレートから `{% section %}` でパーシャルに委譲）
- **paging/**: ファイル分割戦略（クラスごとにファイルパスを定義）

旧設計の toc 層・pages 層・reports 層は廃止。目次（ToC）は出力ツール（Hugo, pandoc 等）の責務。

### ユーザプロジェクト構成

```
my-project/
  model/
    schema/              # スキーマ定義（Validator が読む）
    source/              # ソースデータ（Validator のみが読み書き）
    queries/             # Query 定義：JSONata 式（Validator が評価）
  presentation/
    templates/           # ドキュメントテンプレート（Generator が読む）
    paging/              # ページ分割戦略（Generator が読む）
  output/                # 全て生成物（.gitignore 対象）
    prepared/            # Validator が生成（queries/ の評価結果 YAML）
    documents/           # Generator が生成（Markdown）
    rendered/            # Hugo が生成（HTML）
```

### queries/: データの整形・射影（JSONata）

queries/ は source データを整形・射影し、テンプレートに渡すツリー構造を定義する。
テンプレートエンジンではなく **JSONata**（オブジェクトツリーに対するクエリ＆変換言語）を使用する。

JSONata はオブジェクトツリーに対するクエリ言語であり、JSON というシリアライズ形式とは無関係。
YAML から読み込んだデータに対しても問題なく動作する（JSON データモデル = object / array / string / number / boolean / null のツリー構造に対して操作する）。

```jsonata
// queries/erd.jsonata
{
  "erd": source.entities.category ~> $distinct() ~> $map(function($cat) {
    {
      "key": $cat,
      "title": $cat & " の ER図",
      "entity": source.entities[category = $cat].{
        "key": id,
        "title": name,
        "field": fields
      },
      "relation": source.relations[category = $cat]
    }
  })
}
```

テンプレートエンジン版との比較：

| 観点 | テンプレートエンジン（旧） | JSONata（新） |
|---|---|---|
| データの流れ | データ→テキスト→データ | データ→データ |
| エスケープ | YAML エスケープが必要 | 不要（値はデータのまま流れる） |
| 型の保持 | テキスト経由で劣化の可能性 | 保持される |
| 表現力 | WHERE, DISTINCT 程度 | GROUP BY, JOIN, CROSS JOIN, 集約関数 |

#### JSONata の主要機能（このアプリで使用する範囲）

| SQL 相当 | JSONata の記法 |
|---|---|
| SELECT（射影） | `.{ "key": id, "title": name }` |
| WHERE | `[category = $cat]` |
| DISTINCT | `~> $distinct()` |
| GROUP BY | 重複キーのオブジェクト構築で自動グループ化 |
| ORDER BY | `^(>price, <name)` |
| JOIN | サブクエリとしてネスト |
| CROSS JOIN | `$map` のネストで直積 |
| COUNT / SUM | `$count()`, `$sum()` |
| 文字列結合 | `$cat & " の ER図"` |
| パイプ | `~>` 演算子 |

Python 実装: `jsonata-python`（PyPI、純粋 Python、JSONata 機能 100% カバー）

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

### templates/: 表現

#### root テンプレート

ユーザが必ず書くエントリポイント。ドキュメント全体の構成を定義する：

```jinja2
{# templates/root.md.jinja2 #}
# システム要件定義書

{% section "erd" for prepared.erd %}
{% section "screen" for prepared.screen %}
{% section "usecase" for prepared.usecase %}
```

読者や目的が異なる場合は root テンプレートを分ける（社内向け、顧客向け等）。

#### `{% section %}` カスタムタグ

`{% section %}` は描画をパーシャルテンプレートに委譲する。paging 設定に応じて振る舞いが変わる：

- 対象クラスが paging の分割単位 → 別ファイルに出力し、親にはリンクを残す
- 分割単位でない → インライン展開（通常の `{% include %}` と同等）

```jinja2
{# templates/erd.md.jinja2 #}
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
  root.md.jinja2             → markdown エスケープ
  erd.md.jinja2              → markdown エスケープ
  entity-detail.md.jinja2    → markdown エスケープ
  mermaid-er.mermaid.jinja2  → mermaid エスケープ
```

### paging/: ファイル分割戦略

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

Generator が prepared データのツリーを再帰的に走査し、`key` を持つオブジェクトからフラットマップを自動構築する。

構築手順：

1. ツリー走査 → `key` 持ちオブジェクトの ID（`{class}.{key}`）を収集
2. paging 設定を適用 → 各アンカーが属するページの href を確定
   - paging に該当するクラス → そのページの href
   - 該当しないクラス → 親を辿って最も近い「ページになるアンカー」の href + `#id`
3. テンプレートエンジン起動前にマップ構築を完了させる

テンプレートからは `link_md` フィルタ経由でアクセス。Markdown 内からは `toc:id` 記法でアクセス。

### リンク解決

#### テンプレート内（link_md フィルタ）

```jinja2
{{ "erd.entity.user" | link_md }}
```

→ `[ユーザー](../erd/user-management.md#erd.entity.user)` のような相対リンクを生成。

#### Markdown source 内（toc:id 記法）

```markdown
ユーザーの詳細は[ユーザー](toc:erd.entity.user)を参照。
```

エンジンが `toc:erd.entity.user` をフラットマップから解決し、適切な相対パスに置換する。

## 処理フロー

```
Validator APP:
1. model/source/*.yaml 読み込み → source オブジェクト構築（ruamel.yaml）
2. model/schema/ によるバリデーション
3. model/queries/*.jsonata 評価（source を渡す）→ prepared ツリーを得る
4. output/prepared/*.yaml に書き出し

Generator APP:
5. output/prepared/*.yaml 読み込み
6. ツリー走査 → key 持ちオブジェクトからフラットアンカーマップ構築（ID のみ）
7. paging 設定 × フラットマップ → 各アンカーの href を確定
8. root テンプレートから Jinja2 レンダリング開始
   - {% section %} が paging を参照し、分割 or インライン判定
   - link_md フィルタがフラットマップを参照しリンク生成
9. Markdown 内の toc:id リンクをフラットマップから解決
10. output/documents/ にファイル書き出し

Renderer:
11. Hugo が output/documents/ → output/rendered/ に変換
```

## Validator ↔ Generator インタフェース

Validator と Generator はファイルを介して疎結合に連携する：

```
output/prepared/          # Validator が書き、Generator が読む
  erd.yaml                # queries/erd.jsonata の評価結果
  screen.yaml             # queries/screen.jsonata の評価結果
  ...
```

ファイル方式を選択した理由：

- **デバッグ容易性**: queries/ の評価結果を YAML ファイルとして目視確認できる
- **疎結合**: Validator と Generator が別言語・別プロセスでも動く
- **シンプル**: notify + pull 方式でも結局 Generator 側でデシリアライズが必要。ファイルの方が透明性が高い
- **クリーンビルド**: `rm -rf output/` で全生成物を一括削除できる

## 技術選定

### Python + ruamel.yaml を選択した理由

- **ruamel.yaml のラウンドトリップ保持**: コメント、キー順序、インデント、クォートスタイル、整数/浮動小数の区別を全て保持。MCP 経由で AI が CRUD した際、変更箇所だけが diff に出る
- **Jinja2 の autoescape**: パーシャル単位でエスケープモードを切り替える設計にフィット
- **JSONata の Python 実装**: `jsonata-python`（純粋 Python、機能完全）が利用可能
- **Hugo**: `hugo-python-distributions` で pip install 可能

JavaScript (js-yaml) では:
- 整数と浮動小数の区別が失われる（JavaScript の Number は全て IEEE 754 double）
- コメントが失われる
- YAML を読み込んで書き戻すだけで diff が出る

### クエリ言語の棲み分け

| 用途 | 言語 | 理由 |
|---|---|---|
| MCP API（AI のアドホック CRUD） | JSONPath + JSON Patch | 既存設計（api-design.md）。単純な読み書きに十分 |
| queries/（保存された高度なクエリ） | JSONata | GROUP BY, JOIN, ツリー構築が可能。JSONPath の上位互換的位置付け |

JSONPath は JSONata のサブセット的な位置付け。基本の CRUD は JSONPath で事足り、高度な変換が必要なときだけ JSONata を使う。

### JSON データモデルについての注記

JSONata / JSONPath は「JSON データモデル」（object / array / string / number / boolean / null で構成されるツリー構造）に対して操作するクエリ言語であり、JSON というシリアライズ形式とは無関係。YAML から読み込んだデータに対しても同様に動作する。

なお、「JSON データモデル」という用語に対応する正式な仕様は存在しない（XML には XML Information Set という W3C 勧告があるが、JSON にはそれに相当するものがない）。CBOR の RFC 8949 が "the JSON data model" という表現を使用しており、本ドキュメントでもこれに倣う。

YAML のデータモデルは JSON データモデルのスーパーセット（日付型、整数/浮動小数の区別、アンカー等）だが、このアプリで扱う source データは JSON データモデルの範囲内に収まる。

## TODO

- [ ] **Phase 0-1: JSONata PoC** — example-project の toc/entities.yaml.liquid を JSONata で書き直し、簡潔さとデータ忠実性を検証する
- [ ] example-project でフラットアンカーマップの href 解決を具体例で検証する
  - 特に paging 設定にないクラスの親辿りロジック
- [ ] テンプレートエンジンのエスケープ仕様を確認する（Jinja2）
  - Markdown / Mermaid のエスケープモード切り替え
  - パーシャル単位でエスケープモードを切り替え（拡張子で判定: `.md.jinja2`, `.mermaid.jinja2`）

## 変更履歴

- 2025-03-09: テンプレートエンジンによるデータ変換を JSONata Query Engine に変更。Query Engine を Validator APP に配置。ディレクトリ構成を model/ + presentation/ + output/ の三層に再編。Python + ruamel.yaml の採用理由を追記
- 2025-03-08: 初版。toc 層を reports 層に再設計（テンプレートエンジンによるデータ変換）
