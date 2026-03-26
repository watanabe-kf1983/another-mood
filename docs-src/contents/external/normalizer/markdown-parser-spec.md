# Markdown Parser Specification

Markdown ファイルからデータを抽出するパーサーの仕様。

## 概要

データのフォーマットとして YAML に加えて Markdown も選択可能とする。`contentsDir`（デフォルト: `docs/contents/`）に配置された Markdown ファイルは、Normalizer が内蔵の `prose` スキーマに従って自動的に正規化する。

Markdown は散文（説明文、背景、補足など）の記述に適している。ソース Markdown は普通の Markdown のまま保たれ、GitHub 上でもそのまま閲覧・リンク遷移できる。

## 内蔵 prose スキーマ

Normalizer は Markdown ファイルを以下の構造に変換する:

```yaml
prose:
  - id: "internal/architecture"
    title: "Architecture"
    body:
      _mime_type: text/markdown
      _content: |
        # Architecture

        ## アーキテクチャ概要
        ...
```

| フィールド | 説明 |
|---|---|
| `id` | `contentsDir` からの相対パス（拡張子なし） |
| `title` | H1 見出しから抽出。H1 がなければ null |
| `body` | ファイル全体（H1 含む。title との二重持ち） |

### Typed Value と auto-escape

パイプライン内の値は素の string（デフォルト）または Typed Value オブジェクトのいずれか。テンプレートエンジンはデフォルトで全ての素の string をエスケープする。

Typed Value は `_mime_type` と `_content` を持つオブジェクトで、テンプレート側は値自体を見て判定できる（スキーマ等の外部情報は不要）。`_` プレフィックスのフィールドはシステム予約であり、ユーザ定義のフィールド名と衝突しない:

```yaml
# Typed Value — _mime_type に応じてエスケープをバイパス
body:
  _mime_type: text/markdown
  _content: |
    # Architecture
    ...
```

```yaml
# 素の string — デフォルトでエスケープされる
title: "Architecture"
```

MIME types は [RFC 6838](https://datatracker.ietf.org/doc/html/rfc6838) に準拠する。想定される型: `text/markdown`, `text/html`, `text/plain` 等。

このスキーマはツール内蔵であり、ユーザが `schemaDir` に定義する必要はない。

## セクション単位抽出

`{#id}` 付き見出しがあるファイルでは、ファイル単位レコードに加えてセクション単位のレコードも生成する（ダブルカウント）。

### 入力例

```markdown
# エンティティ定義

## ユーザー {#user-entity}

システムの利用者を表す。

### 補足

管理者ユーザーは追加の権限を持つ。

## 注文 {#order-entity}

ユーザーが商品を購入する際に作成されるトランザクション。
```

### 抽出結果

```yaml
prose:
  # ファイル単位レコード（常に生成）
  - id: "entities"
    title: "エンティティ定義"
    body:
      _mime_type: text/markdown
      _content: |
        # エンティティ定義
        ...（ファイル全体）

  # セクション単位レコード（{#id} があれば生成）
  - id: user-entity
    title: "ユーザー"
    body:
      _mime_type: text/markdown
      _content: |
        システムの利用者を表す。

        # 補足

        管理者ユーザーは追加の権限を持つ。

  - id: order-entity
    title: "注文"
    body:
      _mime_type: text/markdown
      _content: |
        ユーザーが商品を購入する際に作成されるトランザクション。
```

### ID 記法

Pandoc/kramdown 互換の見出し属性記法を使用する:

```markdown
## 見出しテキスト {#id}
```

- `{#id}` の部分がデータの識別子となる
- 見出しテキストは人間用のラベル（`title` として抽出）
- ID は変更しない（安定した識別子）、見出しテキストは変更可能

### 区切り

`{#id}` 属性付き見出しが区切りとなる:

- 見出しレベル（H1〜H6）は問わない
- `{#id}` を持たない見出しは区切りとならない（前のセクションに含まれる）

### 本文範囲

`{#id}` 付き見出しから、次の同レベル以上の `{#id}` 付き見出しまでを本文とする。

### 見出しレベルの正規化

セクション単位レコードの body 内の見出しレベルを正規化する:

- 本文内の最小見出しレベルを H1 にシフト
- 相対関係は維持

例:
```markdown
### 補足

#### 詳細な仕様
```

↓ 正規化 ↓

```markdown
# 補足

## 詳細な仕様
```

テンプレートで使用時に `shiftHeadings(n)` フィルタで調整する。

## リンク正規化

ソース Markdown 内の相対リンクを `toc:` アンカー記法に変換する。

### 変換ルール

1. Markdown リンク `[text](relative/path.md)` を検出
2. 相対パスを `contentsDir` 基点の正規化パスに解決
3. 対応する prose レコードのアンカー ID に変換

### 例

`{contentsDir}/internal/normalizer.md` 内のリンク:

```markdown
処理フローの詳細は[Composer](composer.md)を参照。
[スキーマ仕様](../external/normalizer/schema-spec.md)に従って検証する。
```

↓ 正規化 ↓

```markdown
処理フローの詳細は[Composer](toc:prose.item.internal/composer)を参照。
[スキーマ仕様](toc:prose.item.external/normalizer/schema-spec)に従って検証する。
```

アンカー ID の形式は [anchor-spec.md](../generator/anchor-spec.md) に準拠する。`toc:` リンクの解決は Document Generator が行う（[generator.md](../../internal/components/generator.md) 参照）。

### 背景: ソースの可搬性

ソース Markdown では普通の相対パスでリンクを記述する。これにより:

- GitHub 上でリンクがそのまま動作する
- エディタのリンクジャンプが機能する
- 独自記法によるソース汚染がない

`toc:` 記法への変換は Normalizer が自動的に行うため、ユーザがリンク記法を意識する必要はない。

## 実装方針

- Markdown AST: markdown-it-py（CommonMark 準拠、AST 走査でセクション分割・リンク検出）
- YAML 出力: ruamel.yaml（YAML 1.1、literal block scalar で Markdown 本文を可読に保持）
- 見出しレベル正規化: 自前実装
