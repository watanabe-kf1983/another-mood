# Markdown Parser Specification

## Internal Design

### 実装方針

- Markdown AST: markdown-it-py（CommonMark 準拠、AST 走査でセクション分割・リンク検出）
- YAML 出力: ruamel.yaml（YAML 1.2、literal block scalar で Markdown 本文を可読に保持）
- 見出しレベル正規化: 自前実装

## Proposals

### セクション単位抽出 (A1-A4)

> **未実装** — Phase 13 タスク [A1〜A4](../../../tasks.md)（[A1] `{#id}` 検出 / [A2] 本文範囲切り出し / [A3] ダブル出力 / [A4] 見出しレベル正規化）

`{#id}` 付き見出しがあるファイルでは、ファイル単位レコードに加えてセクション単位のレコードも生成する（ダブルカウント）。

#### 入力例

```markdown
# エンティティ定義

## ユーザー {#user-entity}

システムの利用者を表す。

### 補足

管理者ユーザーは追加の権限を持つ。

## 注文 {#order-entity}

ユーザーが商品を購入する際に作成されるトランザクション。
```

#### 抽出結果

```yaml
prose:
  # ファイル単位レコード（常に生成）
  - id: "entities"
    title: "エンティティ定義"
    body:
      mime_type: text/markdown
      content: |
        # エンティティ定義
        ...（ファイル全体）

  # セクション単位レコード（{#id} があれば生成）
  - id: user-entity
    title: "ユーザー"
    body:
      mime_type: text/markdown
      content: |
        システムの利用者を表す。

        # 補足

        管理者ユーザーは追加の権限を持つ。

  - id: order-entity
    title: "注文"
    body:
      mime_type: text/markdown
      content: |
        ユーザーが商品を購入する際に作成されるトランザクション。
```

#### ID 記法

Pandoc/kramdown 互換の見出し属性記法を使用する:

```markdown
## 見出しテキスト {#id}
```

- `{#id}` の部分がデータの識別子となる
- 見出しテキストは人間用のラベル（`title` として抽出）
- ID は変更しない（安定した識別子）、見出しテキストは変更可能

#### 区切り

`{#id}` 属性付き見出しが区切りとなる:

- 見出しレベル（H1〜H6）は問わない
- `{#id}` を持たない見出しは区切りとならない（前のセクションに含まれる）

#### 本文範囲

`{#id}` 付き見出しから、次の同レベル以上の `{#id}` 付き見出しまでを本文とする。

#### 見出しレベルの正規化

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

この正規化は body を H1 起点に揃えるところまで。テンプレートで埋め込む際の深さ調整は、生成側の `under_heading` フィルタ（[docs/reference/template.md](../../../../docs/reference/template.md#under_heading)）が担う。

### リンク正規化 (A5)

> **未実装** — Phase 11 タスク [A5](../../../tasks.md)

ソース Markdown 内の相対リンクを `node:` アンカーパス記法（インラインリンク形）に変換する。

#### 変換ルール

1. Markdown リンク `[text](relative/path.md)` を検出
2. 相対パスを `contents_dir` 基点の正規化パスに解決
3. 対応する prose レコードのアンカーパス記法 (`node:/...`) に変換

#### 例

`{contents_dir}/design/normalizer/normalizer.md` 内のリンク:

```markdown
処理フローの詳細は[Composer](../composer/composer.md)を参照。
[スキーマ仕様](schema-spec.md)に従って検証する。
```

↓ 正規化 ↓

```markdown
処理フローの詳細は[Composer](node:/prose/design/composer/composer)を参照。
[スキーマ仕様](node:/prose/design/normalizer/schema-spec)に従って検証する。
```

アンカーパスの形式は [anchor-spec.md](../generator/anchor-spec.md) に準拠する。prose はアンカーパスの例外（id 内の `/` を escape せず素通し）が適用されるため、ファイル相対パスがそのままアンカーパスの一部として埋め込まれる。`node:` リンクの解決は Document Generator が pre-render フィルタ `relink` で行う（[generator.md](../generator/generator.md#リンク解決-b4-b5) 参照）。

#### 背景: ソースの可搬性

ソース Markdown では普通の相対パスでリンクを記述する。これにより:

- GitHub 上でリンクがそのまま動作する
- エディタのリンクジャンプが機能する
- 独自記法によるソース汚染がない

`node:` 記法への変換は Normalizer が自動的に行うため、ユーザがリンク記法を意識する必要はない。
