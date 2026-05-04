# Guides

## Another Mood とは

要件定義書、製品カタログ、保守マニュアル、教材 — これらのドキュメントには「ユーザ」「商品」「手順」といった同じ登場人物が、形を変えて何度も出てくる。新しい登場人物を一つ加えるたびに、何か所も直して回り、どこかで直し漏れて、いつの間にか食い違っている。

**Another Mood** は、ソースベース DB のプロセッサで、そういうドキュメント群の整合維持を担うツール。DB のデータを 1 か所直せば、紐付くすべての出力が整合した状態で再生成される — 何か所も直して回らずに済む。

ここでいう **ソースベース DB** とは、ユーザ自身が作成・更新・削除するファイル群 — 以下「**ソース**」と呼ぶ — からなるデータベース。ソースは YAML や Markdown 等の形式で書く（具体的な構成は [ソースの構成](#ソースの構成) で後述）。ユーザがエディタ等でソースを直接書き換えるのが唯一の DB 操作の手段。

Another Mood はそれを読み込み、クエリの実行結果・データの一覧・テンプレートに基づくドキュメントなどを出力する。ユーザはそれらを確認しながら、ソースを書き直し続けることができる。

### 必要なもの

- [uv](https://docs.astral.sh/uv/) — Python パッケージ・プロジェクトマネージャ。

## Quick Start

### インストール

uv をインストールしたうえで:

```bash
uv tool install git+https://github.com/watanabe-kf1983/another-mood.git
```

これで `mood` コマンドが PATH に入る。

### サンプルを起こしてビルド

```bash
mood init my-project
mood build my-project
```

`mood init` でソースベース DB の最小サンプル（メンバー名簿）が `my-project/` 配下に構築される。`mood build` でそれを Markdown と HTML に変換する。

ユーザが書く側（`my-project/` 配下）:

```
my-project/
├── definition/
│   ├── schema.yaml              # データの型
│   ├── queries/by_role.yaml     # ロール別に束ねるクエリ
│   └── templates/
│       ├── index.md             # トップページ
│       ├── member.md            # メンバー詳細
│       └── by_role.md           # ロール別一覧
└── contents/
    └── members.yaml             # 実データ（3 人）
```

ツールが生成する側（`.another-mood/my-project/` 配下）:

```
.another-mood/my-project/
├── output/                                   # Markdown
│   ├── index.md
│   ├── member/{alice,bob,carol}.md
│   ├── by_role/{engineer,designer}.md
│   ├── __meta_entity/                        # 後述
│   ├── __table_view/                         # 後述
│   └── __meta_query/                         # 後述
└── render/                                   # HTML
```

メンバーが 3 人いるので `member/` 配下に 1 ファイルずつ、ロールが 2 種なので `by_role/` 配下に 1 ファイルずつ生成されている。テンプレートの `index.md` がデータをループしながらサブページを書き出す仕組みになっていて、これがこのツールの中核。詳しくは [テンプレート](#テンプレート) 章で。

`__` で始まるディレクトリには、ユーザのテンプレートとは独立にツールが自動生成するページが入る。スキーマ・データ・クエリの現状を書きながら確認するためのもので、[ワークフロー](#ワークフロー) 章で詳述する。

### ライブプレビューで触る

```bash
mood watch my-project
```

`http://localhost:1313` でブラウザに HTML が出る。ファイルを編集して保存すると自動で再ビルド + リロードされる。試しに `contents/members.yaml` の `alice` の `role` を `engineer` から `manager` に変えてみる。`output/by_role/manager.md` が新しく現れて、`output/by_role/engineer.md` から alice が消えるのが見える（ブラウザの対応ページにも同じ変化が出る）。データを 1 行直しただけで、複数のページが整合した状態で再生成された — これがこのツールがやりたいこと。

ここから先は、このサンプルを足がかりに、自分のプロジェクトのソースを書くために必要な道具立てを順に解説する。

## ソースの構成

ソースは 4 種類で構成される。

- **スキーマ** — 構造化データの型を宣言する 1 ファイル。
- **コンテンツ** — 実データ。次の 2 種:
  - **構造化データ** — スキーマに沿って書く YAML。同じ形のレコードの集まり（メンバー一覧、商品一覧、画面定義 …）。
  - **散文** — Markdown でそのまま書く文章。ユーザによるスキーマ宣言は不要（ツール内蔵スキーマで構造化）。
- **クエリ** — 構造化データを加工した結果に名前を付けるビュー。SQL のビューに相当。
- **テンプレート** — 最終出力ページの形を書いたファイル。データやクエリの結果を参照する。

詳しくは [スキーマとコンテンツ](#スキーマとコンテンツ)・[クエリ](#クエリ)・[テンプレート](#テンプレート) で。書く順番と確認の仕方は次節 [ワークフロー](#ワークフロー)。

## ワークフロー

このツールは「テンプレートが完成するまで何も見えない」わけではない。スキーマだけ書いた段階、コンテンツだけ書いた段階、クエリだけ書いた段階、それぞれで「いま自分が書いた分」を確認するページが、ビルドのたび自動で生成される。Quick Start で `__` で始まるディレクトリが出ていたのがそれ。

「どこに書く」のパスはプロジェクトディレクトリ（`<project>/`）からの相対、「どこを確認」のパスは出力先（`.another-mood/<project>/`）からの相対。

| 段階 | 何を書く | どこに書く | どこを確認 |
|---|---|---|---|
| 1 | スキーマ | `definition/schema.yaml` | `output/__meta_entity/<entity>.md` |
| 2 | コンテンツ | `contents/**/*.yaml` (構造化データ)<br>`contents/**/*.md` (散文) | `output/__table_view/<entity>.md` |
| 3 | クエリ | `definition/queries/**/*.yaml` | `output/__meta_query/<query>.md` |
| 4 | テンプレート | `definition/templates/**/*.md` | `output/index.md` 以下 |

スキーマとコンテンツは必須、クエリは省略可、テンプレートは最終出力に必要。`schema.yaml` だけは 1 ファイル固定で、それ以外は複数ファイル・サブディレクトリに自由に分割できる。パスを変更する方法は [CLI](reference/cli.md) を参照。

`mood watch` を回したまま編集すれば、各段の成果が即座にブラウザに出る。テンプレートを書き始める段階では、参照するデータやクエリ結果の形が既に確定しているので、テンプレートに集中できる。ユーザが編集したソースの文法エラーなども同じ仕組みでブラウザに反映されるので、書き手はそれを見ながら直す — この「書く・確認する・直す」ループがワークフローの実際の姿。

### `mood build` と `mood watch` の使い分け

- `mood watch` — エディタで書きながらブラウザで結果を確認したいとき（人間が継続的に書いているとき）に起動して放置する。
- `mood build` — CI で生成だけしたいときや、エージェント（Claude Code 等）が「編集 → ビルド成否を確認 → 次の編集」を回したいときに使う。

使い分けの基準は、エラーを人間が見るか、機械が拾うか。`watch` は人間がコンソール・ブラウザでエラーを見ながら直すためのもの。`build` は完了して結果（成功かエラーか）を返すので、CI やエージェントがそれを判定して次の処理に進める。

## スキーマとコンテンツ

### 構造化データ — スキーマを先に宣言する

メンバー一覧、商品一覧、画面定義、注文履歴 — 「同じ形のレコードが何件もある」種類のデータは、**コンテンツファイル** (`contents/*.yaml`) に書く。ただし、書く前に **スキーマファイル** (`definition/schema.yaml`) でその「形」を宣言しておく。

スキーマ宣言のないデータはビルドエラーになる。同じく、書き間違い（必須フィールド漏れ、型違い、未定義フィールド）もビルド時にエラーで止める。書き手が気付かないまま壊れたデータが下流（クエリ・テンプレート）に流れていくのを、ツール側で防ぐ意図。

スキーマは **JSON Schema** で書く（使える語彙・本家との細かい違いは [Schema](reference/schema.md) を参照）。サンプルのスキーマファイル:

```yaml
type: object
properties:
  members:
    type: object
    additionalProperties:        # ← 「同型エントリのマップ」を意味する
      type: object
      properties:
        name: { type: string }
        role: { type: string }
      required: [name, role]
      additionalProperties: false
additionalProperties: false
```

このスキーマが期待するコンテンツファイルの一例（実際のファイル名は任意）:

```yaml
members:
  alice:
    name: Alice
    role: engineer
  bob:
    name: Bob
    role: engineer
```

ルート構造は固定で、必ず次の 3 点を満たす:

- 最外側は `type: object`
- `properties:` の各エントリが 1 種類の **エンティティ**（同じ形のレコードの集まり）を表す（上の例では `members`）
- 末尾の `additionalProperties: false` で、宣言していないトップレベルキーをエラーにする

エンティティ名（`members`）は、コンテンツファイルのトップレベルキーと一致させる。

各エンティティの中身（`properties` の値）には、定型のパターンが 3 つある — 複数レコードをマップで書く / 複数レコードを配列で書く / 単一レコードを `properties` で列挙。順に見ていく。

#### 複数レコード — マップで書く

メンバー名簿がそのパターン。スキーマの `additionalProperties` の下に値の型を書き、コンテンツファイルはマップ（キーと値のペア）で書く。「同じ形のレコードが何件もある」用途では、ほぼ常にこの **マップパターン** で書く。スキーマファイル抜粋とコンテンツファイルを再掲:

```yaml
# definition/schema.yaml — エンティティ部分の抜粋
members:
  type: object
  additionalProperties:
    type: object
    properties:
      name: { type: string }
      role: { type: string }
    required: [name, role]
    additionalProperties: false
```

```yaml
# コンテンツファイル
members:
  alice:
    name: Alice
    role: engineer
  bob:
    name: Bob
    role: engineer
```

ビルド時にこれは配列に **正規化** され（書いたマップが配列に変換される）、マップのキー（`alice`, `bob`）が各レコードの `id` フィールドとして付与される。テンプレートからは

```yaml
members:
  - { id: alice, name: Alice, role: engineer }
  - { id: bob,   name: Bob,   role: engineer }
```

の形に見える。`id` フィールドはテンプレートからもクエリからも参照でき、ワークフロー表で見たとおり `output/__meta_entity/<entity>.md`（宣言した型がツールにどう解釈されたか）と `output/__table_view/<entity>.md`（データが期待通り読み込まれているか）で確認できる。

マップで書く理由は 2 つ。第一に、レコード数が増えても YAML データの視認性が配列形式より素直（各レコードの先頭に `id` が来て見出しのように働く）。第二に、`id` の一意性が YAML パースの段階で保証されるため、同じキーがあれば即パースエラーになり、後から「`id` が衝突していました」と気付かされない。

#### 複数レコード — 配列で書く

逆に、上の 2 つの利点（視認性・ID 一意性）が要らないなら、`type: array` で配列（順序のある並び）として書いてもよい。たとえば順序だけが意味を持つ手順、外部から個別参照されない注釈の列、ID を考えるのが面倒なほど些末なレコードの羅列、など。

```yaml
# definition/schema.yaml — エンティティ部分
steps:
  type: array
  items:
    type: object
    properties:
      label: { type: string }
    required: [label]
    additionalProperties: false
```

```yaml
# コンテンツファイル
steps:
  - label: Boil water
  - label: Add tea leaves
  - label: Wait 3 minutes
```

マップパターンと違って正規化はされず、書いた配列がそのままテンプレートに渡る。

#### 単一レコード — `properties` で列挙

サイト設定のように「キーが事前に決まっていて、レコード数が 1 つ」のものは、`additionalProperties` の代わりに `properties` でキーを列挙する:

```yaml
# definition/schema.yaml に追加
site_config:
  type: object
  properties:
    title: { type: string }
    base_url: { type: string }
  additionalProperties: false
```

```yaml
# コンテンツファイル
site_config:
  title: My Site
  base_url: https://example.com
```

配列同様、正規化されず、書いた形のままテンプレートに渡る。

#### コンテンツファイル — 名前と分割は自由

これまで説明したとおり、データの内容はスキーマファイルで定義した JSON Schema の制約に従う。しかし、コンテンツファイル自体の整理（ファイル名・ディレクトリ構成・ファイル数）には制約がない。ドメイン別・章別・レビュー単位別など、プロジェクトに合った粒度で整理してよい:

- サブディレクトリに置いてよい
- ファイル名・ディレクトリ名はエンティティ名と一致させなくてよい
- 1 ファイルに複数のエンティティのデータを書いてよい
- 1 つのエンティティのデータを複数ファイルに分割してよい

ビルド時にすべての YAML がマージされ、各ファイルの **トップレベルキー** でエンティティに紐付けられる。

### 散文 — Markdown でそのまま書く

「同じ形のレコードが何件もある」種類のデータは構造化データとして YAML で書く一方、**定型の枠に収まらない長めの散文** は YAML には収まりにくい。説明文・背景・補足、FAQ、ガイド、ヘルプ記事など、Markdown でそのまま書きたい類のものがそれ。

こうした散文を書くときは、ユーザはスキーマを宣言せず、`contents/` 配下に `.md` で置くだけでよい。**ツール内蔵のスキーマ** が暗黙に適用される（次の YAML 例で具体形を示す）。

たとえば `contents/guides/ordering.md` をこう書いたとする:

```markdown
# 注文の流れ

カートに商品を入れて、レジに進むと…
```

テンプレートからは、**予約名 `prose`** の配列にレコードが現れる:

```yaml
prose:
  - id: guides/ordering          # ファイルの相対パス（拡張子なし）
    title: 注文の流れ              # 最初の H1
    body:                        # ファイル全体の Markdown
      mime_type: text/markdown
      content: |
        # 注文の流れ

        カートに商品を入れて、レジに進むと…
```

1 ファイル = 1 レコードで、`id` / `title` / `body` の 3 フィールドが内蔵スキーマで定義されている。`body` が `mime_type` と `content` の入れ子になっているのは Typed Value の形式（[テンプレート](#テンプレート) 章で詳述）。

## クエリ

クエリは、構造化データを参照しやすい形に加工する仕組み。加工結果は **ビュー** として名前が付き、構造化データと同じようにテンプレートから参照できる。必要に応じて追加する。

クエリを書く場面は、グループ化（カテゴリ別 / ロール別 …）、フィールドの絞り込み・リネーム、同じ加工結果を複数のテンプレートで使い回す、といったところ。

### 例: ロール別グループ化

メンバー名簿サンプルに含まれているクエリの例。元データ（[スキーマとコンテンツ](#スキーマとコンテンツ) 章で正規化された `members`）は次の形:

```yaml
members:
  - { id: alice, name: Alice, role: engineer }
  - { id: bob,   name: Bob,   role: engineer }
  - { id: carol, name: Carol, role: designer }
```

これを `role` でグループ化するクエリ:

```yaml
# definition/queries/by_role.yaml
by_role:                  # ← ファイルのトップレベルキーがビュー名になる
  from: members           # 元データ
  grouped:
    by: role              # グループ化のキー
  select:
    - item: role
      as: id              # role を id フィールドにする
    - item: role
    - item: members
```

これでビュー `by_role` ができる。テンプレートからは

```yaml
by_role:
  - id: engineer
    role: engineer
    members:
      - { id: alice, name: Alice, role: engineer }
      - { id: bob,   name: Bob,   role: engineer }
  - id: designer
    role: designer
    members:
      - { id: carol, name: Carol, role: designer }
```

の形に見える。

### クエリで使われる語彙の全体像

クエリは `from` → `grouped`（任意）→ `select`（任意）の 3 ブロック構成。

| ブロック | 役割 |
|---|---|
| `from` | 元データを指定する。ドット記法で入れ子データを取り出すこともできる（詳細はリファレンス） |
| `grouped` | `by` で指定したフィールド値が同じレコードを 1 つにまとめる |
| `select` | 出力に含めるフィールドを列挙。`as` でリネームできる |

`definition/queries/` 配下のファイル名・分割はコンテンツファイル同様、自由（1 ファイルに複数ビュー可、サブディレクトリ可）。

全構文・例は [Query](reference/query.md) を参照。

## テンプレート

テンプレートは、データやビューをユーザがページとしてカスタマイズして整形出力する仕組み。記法は、このツールが利用しているテンプレートエンジン [Jinja2](https://jinja.palletsprojects.com/) の記法と、このツールの独自記法（ファイル分割のためのタグ `{% mood_view %}`）からなる。

### Jinja2 の基本記法

最低限以下を押さえておく:

- `{{ x }}` — 値を埋め込む
- `{% for x in xs %}...{% endfor %}` — 繰り返し
- `{% if x %}...{% endif %}` — 条件分岐
- `{# ... #}` — コメント

全構文は [Jinja2 公式ドキュメント](https://jinja.palletsprojects.com/) を参照。

### ルートテンプレート

`definition/templates/index.md` がサイトの入口（ルートテンプレート）。テンプレートエンジンはここから評価を始める。トップページの本文と、サブページを生成するための `{% mood_view %}` 呼び出しを書く。

サンプルの `definition/templates/index.md`:

```jinja2
# Project Members

## Members

{%- for member in members %}
- [{{ member.name }}](member/{{ member.id }}.md)
{%- endfor %}

{%- for member in members -%}
{% mood_view "member" with member %}
{%- endfor %}

## By Role

{%- for entry in by_role %}
- [{{ entry.role }}](by_role/{{ entry.id }}.md)
{%- endfor %}

{%- for entry in by_role -%}
{% mood_view "by_role" with entry %}
{%- endfor %}
```

各セクションに `for` ループが 2 回出てくる。前半は **目次のリンクを出す** ループ、後半は **サブページ本体を書き出す** ループ。

これは `{% mood_view %}` の動作によるもの。`{% mood_view "TEMPLATE_NAME" with DATA %}` は、`definition/templates/<TEMPLATE_NAME>.md` を `DATA` で評価して別ファイルに書き出すタグで、タグ自体は **空文字列を返す**（書き出しは副作用）。親ページの目次リンクは別途 Markdown のリンク記法で書く必要があるため、リンク用と本文生成用にループが分かれる。

出力ファイル名は `DATA` に `id` フィールドがあるかで決まる:

| `DATA` の中身 | 出力先 |
|---|---|
| `id` を含むマップ | `<TEMPLATE_NAME>/<id>.md` |
| `id` がないマップ | `<TEMPLATE_NAME>.md` |

サンプルの `{% mood_view "member" with member %}` は、`member.id` が `alice` なら `member/alice.md` に書き出される。クエリで `as: id` を付けて id を作っておくと、`mood_view` の結果がロール別に 1 ファイルに分かれる、という流れがここで完結する。

`{% mood_view %}` はサブテンプレートからも呼び出せる（サブページの中でさらにサブページを生成できる）。タグの全仕様は [Template — Jinja2 拡張](reference/template.md#jinja2-拡張-mood_view)。

### サブテンプレート

`{% mood_view %}` から呼び出される側のテンプレート。`with` で渡したマップのフィールドがそのままトップレベル変数として使える:

```jinja2
{# definition/templates/member.md #}
# {{ name }}

Role: {{ role }}
```

### Markdown 本文を埋め込む（Typed Value）

散文の `body` フィールドは、`mime_type` と `content` を持つマップ（**Typed Value**）になっている。テンプレートで本文を埋め込むときは `.content` を参照する:

```jinja2
{# 散文の本文を埋め込む #}
{{ body.content }}
```

詳細は [Template — Typed Value の取り扱い](reference/template.md#typed-value-の取り扱い)。

### 未定義フィールドは空文字列になる

```jinja2
| {{ member.id }} | {{ member.metadata.title }} |
```

`metadata` が無い場合も、あっても `title` が無い場合も、エラーにならず **空文字列** になる。

ただし、スペルミスのときも同じくエラーにならず黙って空になる点に注意。書きながら `__table_view/` でデータの実体を、`__meta_query/` でクエリの結果形を確認しながら進める（[ワークフロー](#ワークフロー)）。

## 次に読むもの

- [リファレンス](reference/index.md) — 各機能の構文・全オプション・予約語
- [showcase/examples/ecommerce/](../showcase/examples/ecommerce/) — メンバー名簿より複雑な動くサンプル（EC サイト想定で entities / relations / 散文 / クエリ / テンプレートを一通り使う）
