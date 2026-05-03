# Guides

## another-mood とは

要件定義書、製品カタログ、保守マニュアル、教材 — これらのドキュメントには「ユーザ」「商品」「手順」といった同じ登場人物が、形を変えて何度も出てくる。新しい登場人物を一つ加えるたびに、何か所も直して回り、どこかで直し漏れて、いつの間にか食い違っている。

**another-mood** は、ソースベース DB のプロセッサで、そういうドキュメント群の整合維持を担うツール。DB のデータを 1 か所直せば、紐付くすべての出力が整合した状態で再生成される — 何か所も直して回らずに済む。

ここでいう **ソースベース DB** とは、ユーザ自身が作成・更新・削除するファイル群 — 以下「**ソース**」と呼ぶ — からなるデータベース。ソースは YAML や Markdown 等の形式で書く（具体的な構成は [ソースの構成](#ソースの構成) で後述）。ユーザがエディタ等でソースを直接書き換えるのが唯一の DB 操作の手段。

another-mood はそれを読み込み、クエリの実行結果・データの一覧・テンプレートに基づくドキュメントなどを出力する。ユーザはそれらを確認しながら、ソースを書き直し続けることができる。

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
  - **散文** — Markdown でそのまま書く文章。スキーマ宣言は不要。
- **クエリ** — 構造化データを加工した結果に名前を付けるビュー。SQL のビューに相当。
- **テンプレート** — 最終出力ページの形を書いたファイル。データやクエリを参照する。

詳しくは [コンテンツとスキーマ](#コンテンツとスキーマ)・[クエリ](#クエリ)・[テンプレート](#テンプレート) で。書く順番と確認の仕方は次節 [ワークフロー](#ワークフロー)。

## ワークフロー

このツールは「テンプレートが完成するまで何も見えない」わけではない。スキーマだけ書いた段階、データだけ書いた段階、クエリだけ書いた段階、それぞれで「いま自分が書いた分」を確認するページが、ビルドのたび自動で生成される。Quick Start で `__` で始まるディレクトリが出ていたのがそれ。

「どこに書く」のパスはプロジェクトディレクトリ（`<project>/`）からの相対、「どこを確認」のパスは出力先（`.another-mood/<project>/`）からの相対。

| 段階 | 何を書く | どこに書く | どこを確認 | 何を確認 |
|---|---|---|---|---|
| 1 | スキーマ | `definition/schema.yaml` | `output/__meta_entity/<entity>.md` | 宣言した型がツールにどう解釈されたか |
| 2 | コンテンツ | `contents/**/*.yaml` (構造化データ)<br>`contents/**/*.md` (散文) | `output/__table_view/<entity>.md` | データが期待通り読み込まれているか |
| 3 | クエリ | `definition/queries/**/*.yaml` | `output/__meta_query/<query>.md` | クエリの結果がどんな形か |
| 4 | テンプレート | `definition/templates/**/*.md` | `output/index.md` 以下 | 最終ユーザ向けのページ |

スキーマとコンテンツは必須、クエリは省略可、テンプレートは最終出力に必要。`schema.yaml` だけは 1 ファイル固定で、それ以外は複数ファイル・サブディレクトリに自由に分割できる。パスを変更する方法は [CLI](reference/cli.md) を参照。

`mood watch` を回したまま編集すれば、各段の成果が即座にブラウザに出る。テンプレートを書き始める段階では、参照するデータ・クエリの形が既に確定しているので、テンプレートに集中できる。ユーザが編集したソースの文法エラーなども同じ仕組みでブラウザに反映されるので、書き手はそれを見ながら直す — この「書く・確認する・直す」ループがワークフローの実際の姿。

### `mood build` と `mood watch` の使い分け

- `mood watch` — エディタで書きながらブラウザで結果を確認したいとき（人間が継続的に書いているとき）に起動して放置する。
- `mood build` — CI で生成だけしたいときや、エージェント（Claude Code 等）が「編集 → ビルド成否を確認 → 次の編集」を回したいときに使う。

使い分けの基準は、エラーを人間が見るか、機械が拾うか。`watch` は人間がコンソール・ブラウザでエラーを見ながら直すためのもの。`build` は完了して結果（成功かエラーか）を返すので、CI やエージェントがそれを判定して次の処理に進める。

## コンテンツとスキーマ

書き手が手で書くコンテンツは、構造化データ（YAML）と散文（Markdown）の 2 種。書き方が違うので別々に説明する。

### 構造化データ — スキーマを先に宣言する

メンバー一覧、商品一覧、画面定義、注文履歴 — 「同じ形のレコードが何件もある」種類のデータは、`contents/*.yaml` に書く。ただし、書く前に `definition/schema.yaml` でその「形」を宣言しておく。

先にスキーマを宣言する理由は 2 つ。(1) 書き間違い（必須フィールド漏れ、型違い、未定義フィールド）がビルド時にエラーになる。(2) クエリやテンプレートが「何が来るか」を前提に書ける。

サンプルの `schema.yaml`:

```yaml
type: object
properties:
  members:
    type: object
    additionalProperties:        # ← 「同型エントリの辞書」を意味する
      type: object
      properties:
        name: { type: string }
        role: { type: string }
      required: [name, role]
      additionalProperties: false
additionalProperties: false
```

ルートは `type: object` 固定で、`properties:` の各エントリ（上の例では `members`）が「全コンテンツに登場する 1 種類のエンティティ」になる。ここでの `members` という名前は、コンテンツ側の YAML のトップレベルキーと一致させる。

#### 辞書で書くか、リストで書くか

「同じ形のレコードが何件もある」用途では、ほぼ常に **辞書パターン** で書く。スキーマの `additionalProperties` の下に値の型を書き、コンテンツ側は辞書で書く。サンプルの `members.yaml` がその例:

```yaml
members:
  alice:
    name: Alice
    role: engineer
  bob:
    name: Bob
    role: engineer
```

ビルド時にこれは配列に正規化され、辞書のキー（`alice`, `bob`）が各レコードの `id` フィールドとして付与される。テンプレートからは

```yaml
members:
  - { id: alice, name: Alice, role: engineer }
  - { id: bob,   name: Bob,   role: engineer }
```

の形に見える。

辞書で書かせている理由は、ID の一意性が YAML パースの段階で保証されるため。同じキーがあれば即パースエラーになるので、後から「ID が衝突していました」と気付かされない。リスト形式（`type: array`）も書けるが、ID の重複を自分で防ぐ必要が出てくるので、ID を持たせたい場合は辞書パターンを使う。

#### 1 つきりのデータ

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
# contents/site_config.yaml
site_config:
  title: My Site
  base_url: https://example.com
```

このパターンは正規化されず、書いた形のままテンプレートに渡る。

スキーマで使えるキーワードの全量・型システムの細かい挙動は [Schema](reference/schema.md) を参照。

### 散文 — Markdown でそのまま書く

説明文・背景・補足のような散文は、スキーマを宣言する必要がない。`contents/` 配下に `.md` で置けば、それだけで読み込まれる。

たとえば `contents/guides/ordering.md` を置くと、テンプレートからは `prose` という名前のリストにレコードが現れる。1 ファイル = 1 レコードで、`id` はファイルの相対パス（拡張子なし）、`title` は最初の `# H1`、`body` はファイル全体の Markdown:

```jinja2
{% for record in prose %}
## {{ record.title }}
{{ record.body.content }}
{% endfor %}
```

散文に専用形式を要求しない理由は、Markdown ソースを GitHub や IDE で素のまま読みたい場面が多いため。専用形式を強制すると、ツールがないと読めない散文になってしまう。「ファイルを開けばそのまま読める」状態を優先している。

詳細（front matter の扱い、`mime_type` の意味）は [Content Formats](reference/content-formats.md) を参照。

### ファイル分割は自由

形式（YAML / Markdown）によらず、`contents/` 配下では:

- サブディレクトリに置いてよい
- ファイル名・ディレクトリ名はスキーマ名と一致させなくてよい
- 1 ファイルに複数のスキーマのデータを書いてよい
- 1 つのスキーマのデータを複数ファイルに分割してよい

ビルド時にすべてのファイルがマージされ、各ファイルの **トップレベルキー** でスキーマに紐付けられる。書き手の整理軸（ドメイン別、章別、レビュー単位別 …）はプロジェクトごとに違うので、ツール側からは命名規約で縛らない方針。

## クエリ

データがそろってきて、いざテンプレートを書こうとすると、「データのままじゃ困る」ケースに当たる:

- メンバーをロール別にグループ化して、ロールごとに 1 ページずつ作りたい
- 画面定義に入れ子で並んでいるボタンを、画面横断の 1 つの一覧として出したい
- 全エンティティから PK を持つフィールドだけを取り出した表を出したい

これらをテンプレート側で書こうとすると、Jinja2 の式が膨らみ、似たコードが複数のテンプレートに散らばる。クエリは「データを加工した結果に名前を付けて、データと同じ感覚でテンプレートから参照できるようにする」レイヤ。SQL で言えばビュー定義に当たる。

### 書かなくて済むなら書かない

スキーマで宣言した形そのままでテンプレートに渡して困らないなら、クエリは書かなくていい。`for` + 単純な `if` で済む範囲のことをわざわざクエリに切り出す必要はない。クエリを書く場面は、

- グループ化（カテゴリ別 / ロール別 / 月別 …）
- 子エンティティを親から外してフラットな配列にする
- フィールドの射影（出力に含めるフィールドを絞る、リネームする）
- 同じ加工結果を複数のテンプレートで使い回す

あたりに限られる。

### グループ化の例

サンプルに含まれているクエリ:

```yaml
# definition/queries/by_role.yaml
by_role:                  # ← ファイルのトップレベルキーがビュー名になる
  from: members           # 元データ
  grouped:
    by: role              # グループ化のキー
  select:
    - item: role
      as: id              # （理由は次節）
    - item: role
    - item: members
```

これでビュー `by_role` ができる。テンプレートから読むと、

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

という形のデータが入っている。

`as: id` を付けているのには理由がある。テンプレート側でこのビューを使って「ロール別ページを 1 ロール 1 ファイルで出力」したい（[テンプレート](#テンプレート) 章で詳述）。サブページに分けるには、各エントリに `id` フィールドが必要。`id` を付けないと、出力が 1 ファイルに集約されてしまう。

`select` を省略すると、各レコードから何も取り出さない（空オブジェクトの配列が返る）ので、テンプレートに渡したいフィールドは必ず `select` で明示する。

### 親子のフラット化

別の例として、画面定義にボタンが入れ子になっている状況を考える:

```yaml
# definition/schema.yaml（抜粋）
screens:
  type: object
  additionalProperties:
    type: object
    properties:
      title: { type: string }
      buttons:
        type: object
        additionalProperties:
          type: object
          properties:
            label: { type: string }
          additionalProperties: false
    additionalProperties: false
```

「全画面のボタンを横断した一覧」を出したいなら:

```yaml
# definition/queries/all_buttons.yaml
all_buttons:
  from: screens.buttons
```

`from` のドット記法は、各セグメントを順に展開して flatten する操作。任意の深さまで連結できる（`from: a.b.c.d`）。SQL の JOIN とは逆方向（親から子を展開する）の操作。

DSL の全構文は [Query DSL](reference/query-dsl.md) を参照。

### テンプレートから見える名前空間

テンプレートからデータを参照するとき、正規化済みデータもクエリビューも散文も、すべて同じ名前空間に並ぶ:

| 種類 | テンプレートでの参照名 |
|---|---|
| 正規化済みデータ | スキーマで宣言したエンティティ名（`members`, `screens` …） |
| クエリビュー | クエリファイルのトップレベルキー（`by_role`, `all_buttons` …） |
| 散文 | `prose`（固定） |

```jinja2
{% for member in members %}        {# データ #}
{% for entry in by_role %}         {# クエリビュー #}
{% for record in prose %}          {# 散文 #}
```

テンプレート側はデータの出所を意識する必要がなく、書きながら「やっぱりデータをクエリ経由に置き換える」とした場合も、参照名が変わるだけでテンプレートの書き方は同じ。

## テンプレート

データもクエリもそろった。あとは、それを使ってどんな形のページを出すかをテンプレートで決める。テンプレートは Jinja2 をベースに、ファイルを分割するための独自タグ `{% mood_view %}` を加えたもの。

### `index.md` から始まる

テンプレートエンジンは `templates/index.md` から評価を始める。ここに「目次」と「各サブページの呼び出し」を書き、サブページの本文は別のテンプレートファイルに分けて `{% mood_view %}` から呼び出す。

サンプルの `templates/index.md`:

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

各セクションに `for` ループが 2 回出てくる。前半は **目次のリンクを出す** ループ、後半は **サブページ本体を書き出す** ループ。ループが 2 つに分かれているのは、`{% mood_view %}` タグ自体は本文に何も出力しない（副作用としてサブページを書き出すだけ）ため。リンクと本文の両方が欲しいので、両方をループする。

`templates/index.md` を起点に固定しているのは、サイト全体の入口を 1 つに定めるため。読者・別の書き手・LLM のいずれにとっても「最初に読むファイル」を探さなくてよい。

### `{% mood_view %}` でサブページを書き出す

```jinja2
{% mood_view "TEMPLATE_NAME" with DATA %}
```

`templates/<TEMPLATE_NAME>.md` を `DATA` で評価して、別ファイルに書き出す。タグ自体は **空文字列を返す**（書き出しは副作用）。

出力ファイル名は `DATA` に `id` フィールドがあるかで決まる:

| `DATA` の中身 | 出力先 |
|---|---|
| `id` を含む辞書 | `<TEMPLATE_NAME>/<id>.md` |
| `id` がない辞書 | `<TEMPLATE_NAME>.md` |

サンプルの `{% mood_view "member" with member %}` は、`member.id` が `alice` なら `member/alice.md` に書き出される。「クエリで `as: id` を付けて id を作っておく」 →「テンプレートで `mood_view` した結果がロールごとに 1 ファイルに分かれる」という流れがここで完結する。

サブテンプレート側（`templates/member.md`）では、`with` で渡した辞書のフィールドがそのままトップレベル変数として使える:

```jinja2
{# templates/member.md #}
# {{ name }}

Role: {{ role }}
```

親ページからのリンクは `{% mood_view %}` の外に書く必要がある。タグ自体は何も出力しないので、目次リンクは別途 Markdown のリンク記法で書く。サンプルでリンクのループとサブページ生成のループが分かれているのはこのため。

タグの全仕様は [Template — Jinja2 拡張](reference/template.md#jinja2-拡張-mood_view)。

### Markdown 本文を埋め込む（Typed Value）

散文 Markdown の本文や HTML 断片を埋め込むときに困るのは、Jinja2 がデフォルトで `{{ x }}` を HTML エスケープすること。Markdown ソースの `# Heading` が `&#35; Heading` になってしまう。

そこで、Markdown / HTML のような「すでに整形済みの値」は `{ mime_type, content }` 形式のオブジェクト（**Typed Value**）で持っておき、テンプレートでは `.content` を参照する:

```jinja2
{# 散文 prose の本文を埋め込む #}
{{ body.content }}
```

`mime_type` が `text/markdown` ならエスケープをバイパスして Markdown のまま埋め込まれる。詳細は [Content Formats — Typed Value](reference/content-formats.md#typed-value)。

### 存在しない値を参照しても落ちない

```jinja2
| {{ member.id }} | {{ member.metadata.title }} |
```

`metadata` が無い場合も、あっても `title` が無い場合も、エラーにならず **空文字列** になる。

これは、スキーマで `required` に挙げていないフィールドが、データ側で省略され得るため。Jinja2 のデフォルト（Undefined でエラー）だと、optional なフィールドごとに `{% if x is defined %}` でガードする必要があり、テンプレートが急速に膨れる。空文字フォールバックでテンプレートを薄く保ち、データの有無に対する寛容さを表現層のデフォルトにしている。

代償として、スペルミスもエラーにならず黙って空になる。これは、書きながら `__table_view/` でデータの実体を見て、`__meta_query/` でクエリの結果形を確認する書き進め方（[ワークフロー](#ワークフロー)）でカバーする想定。

## 次に読むもの

- [Reference](reference/index.md) — 各機能の構文・全オプション・予約語
- [showcase/examples/ecommerce/](../showcase/examples/ecommerce/) — メンバー名簿より複雑な動くサンプル（EC サイト想定で entities / relations / 散文 / クエリ / テンプレートを一通り使う）
