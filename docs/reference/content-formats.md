# Content Formats

`{project}/contents/` 配下に置いたファイルがコンテンツとして読み込まれる。扱える種類は **構造化データ** と **散文データ** の 2 つ。

## 構造化データ

ユーザ、注文、画面定義など、構造が決まったデータは **YAML** で書く。拡張子 `.yaml` または `.yml`（大小文字不問）のファイルが読み込まれる。

ファイルのトップレベルキーは**スキーマ名**に一致する。キーの下にどんな形で値を書くかは、スキーマで宣言した形に対応して決まる（[Schema](schema.md#サポートするキーワード) 参照）。

### 辞書パターンのコンテンツ

[辞書パターン](schema.md#辞書パターンadditionalproperties)に対応するコンテンツ。辞書形式で書く。

```yaml
# contents/users.yaml
users:
  tanaka:
    name: 田中太郎
    email: tanaka@example.com
  suzuki:
    name: 鈴木花子
```

正規化で配列にフラット化され、辞書キーが `id` フィールドに入る:

```yaml
users:
  items:
    - id: tanaka
      name: 田中太郎
      email: tanaka@example.com
    - id: suzuki
      name: 鈴木花子
```

**ネスト**: スキーマ側で入れ子の `additionalProperties` を定義している場合、コンテンツ側も入れ子の辞書で書く。各階層が再帰的に配列化される。

```yaml
# contents/screens.yaml
screens:
  user-screen:
    title: ユーザー画面
    buttons:
      save:
        label: 保存
      cancel:
        label: キャンセル
```

### 固定構造パターンのコンテンツ

[固定構造パターン](schema.md#固定構造パターンproperties)に対応するコンテンツ。スキーマが定めたキーをそのまま書く。正規化は行われず、書いた形のままパススルーされる。

```yaml
# contents/site_config.yaml
site_config:
  title: My Site
  base_url: https://example.com
```

### type: array のコンテンツ

[type: array](schema.md#type-array) に対応するコンテンツ。配列を直接書く。辞書パターンと違い、暗黙の `id` は付かない。

```yaml
# contents/tags.yaml
tags:
  - name: important
  - name: draft
```

## 散文データ

説明文・背景・補足などの散文は **Markdown** で書く。拡張子 `.md`（大小文字不問）のファイルが読み込まれ、内蔵の `prose` スキーマに従って自動変換される。スキーマをユーザが宣言する必要はない。

ソース Markdown は普通の Markdown のまま保たれるので、GitHub 上や IDE でそのまま閲覧・リンク遷移できる。クエリ・テンプレートからの参照方法は [Query DSL](query-dsl.md) と [Template](template.md) を参照。

### 変換ルール

1 ファイル = 1 レコード（ファイル単位レコード）として、以下の構造に変換される:

```yaml
prose:
  - id: "internal/architecture"        # contents_dir からの相対パス（拡張子なし）
    title: "Architecture"              # 最初の H1 見出しテキスト
    body:
      mime_type: text/markdown
      content: |
        # Architecture
        ...                             # ファイル全体（H1 含む）
```

| フィールド | 値 |
|---|---|
| `id` | `contents_dir` からの相対パス（拡張子を除く） |
| `title` | 最初の H1 見出しテキスト。H1 がなければ省略 |
| `body` | Typed Value。`mime_type: text/markdown` と `content`（ファイル全体）を持つ |

### Typed Value

値は素の string（デフォルト）または **Typed Value** オブジェクトのいずれかで表現される。Typed Value は `mime_type` と `content` の 2 フィールドを持つオブジェクトで、テンプレートエンジンの auto-escape を制御する。

| 値の形 | テンプレートでの扱い |
|---|---|
| 素の string | デフォルトでエスケープされる |
| Typed Value（`mime_type: text/markdown` 等） | `mime_type` に応じてエスケープをバイパス |

Markdown ファイルから変換された `body` は Typed Value として格納されるため、テンプレートに埋め込んだ際に HTML エスケープされずに Markdown として解釈される。

`mime_type` は [RFC 6838](https://datatracker.ietf.org/doc/html/rfc6838) に準拠。想定値: `text/markdown` / `text/html` / `text/plain` 等。

**YAML で直接書くこともできる**（スキーマ側でフィールドの型をオブジェクトとして定義しておく）:

```yaml
description:
  mime_type: text/markdown
  content: |
    **重要**: ここは Markdown として解釈される
```

## ファイル構成の自由度

形式によらず共通のルール:

- サブディレクトリに置いても読まれる
- ファイル名・ディレクトリ構成はスキーマ名と対応する必要はない。ビルド時に全ファイルがマージされ、各ファイルのトップレベルキーによってスキーマに紐付く

したがって:

- 1 ファイルに複数スキーマのデータを書いてもよい
- **1 つのスキーマのデータを複数ファイルに分割して書いてもよい**（サブディレクトリ分けも自由）
