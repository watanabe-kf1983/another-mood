# Markdown Parser Specification

Markdownファイルからデータを抽出するパーサーの仕様。

## 概要

データのフォーマットとしてYAMLに加えてMarkdownも選択可能とする。
Markdownは散文（説明文、背景、補足など）の記述に適している。

## 抽出ルール

### ID記法

Pandoc/kramdown 互換の見出し属性記法を使用する：

```markdown
## 見出しテキスト {#id}
```

- `{#id}` の部分がデータの識別子となる
- 見出しテキストは人間用のラベル（抽出対象外）
- IDは変更しない（安定した識別子）、見出しテキストは変更可能

### 自動ID生成

`{#id}` が省略された場合、見出しテキストからIDを自動生成する。

#### ID解決の優先順位

1. `{#id}` 属性があればそれを使う
2. なければ見出しテキストから自動生成

#### 自動生成ルール（設定で切り替え可能）

```yaml
# reqs-builder.config.yaml
markdown:
  autoIdType: "github"  # デフォルト
```

| 設定値 | 動作 | 例 |
|--------|------|-----|
| `github` | GitHub互換（小文字化、スペース→ハイフン、非ASCII除去） | `User Management` → `user-management` |
| `unicode` | 見出しテキストをそのままID（日本語OK） | `ユーザー管理` → `ユーザー管理` |

#### GitHub互換ルールの詳細

1. 小文字化
2. スペースをハイフンに変換
3. 特殊文字（記号等）を除去
4. 連続ハイフンは1つに
5. 重複時は `-1`, `-2` を付与

#### 注意事項

- 日本語見出しで `github` ルールを使うとIDが空になる（警告を出力）
- 日本語中心のプロジェクトでは `unicode` または明示的な `{#id}` を推奨

### 区切り

見出しで区切る。

- 見出しレベル（H1〜H6）は問わない
- `{#id}` 属性付き、または自動ID生成対象の見出しが区切りとなる

### 本文範囲

`{#id}` 付き見出しから、次の同レベル以上の見出しまでを本文とする。

```markdown
## ユーザー {#user-entity}

説明文

### 属性について

属性の詳細...

## 注文 {#order-entity}
```

この場合、`{#user-entity}` の本文は「説明文 + ### 属性について + 属性の詳細...」となる。

### 見出しレベルの正規化

抽出した本文内の見出しレベルを正規化する。

- 本文内の最小見出しレベルをH1にシフト
- 相対関係は維持

例：
```markdown
### 属性について

#### 詳細な仕様
```

↓ 正規化 ↓

```markdown
# 属性について

## 詳細な仕様
```

テンプレートで使用時に `shiftHeadings(n)` フィルタで調整する。

## 抽出結果

```yaml
markdown-descriptions:
  - id: user-entity
    body: |
      説明文

      # 属性について

      属性の詳細...
  - id: order-entity
    body: |
      注文の説明...
```

- `id`: 見出しの `{#id}` 属性から抽出
- `body`: 本文（正規化済み）

## 使用例

### 入力ファイル（source/descriptions.md）

```markdown
# エンティティ定義

このドキュメントは各エンティティの説明を記述する。

## ユーザー {#user-entity}

システムの利用者を表す。認証にはメールアドレスを使用する。

### 補足

管理者ユーザーは追加の権限を持つ。

## 注文 {#order-entity}

ユーザーが商品を購入する際に作成されるトランザクション。
```

### YAMLデータとの紐付け

```yaml
# source/entities.yaml
entities:
  - id: user-entity
    name: ユーザー
    attributes:
      - name: id
        type: integer
      - name: email
        type: string
  - id: order-entity
    name: 注文
    attributes:
      - name: id
        type: integer
```

### テンプレートでの使用

```liquid
{% for entity in entities %}
{% set desc = markdownDescriptions | selectById(entity.id) %}
## {{ entity.name }}

{{ desc.body | shiftHeadings(2) }}

### 属性一覧

| 属性名 | 型 |
|--------|-----|
{% for attr in entity.attributes %}
| {{ attr.name }} | {{ attr.type }} |
{% endfor %}

{% endfor %}
```

## 実装方針

- `remark-parse` でMarkdownをAST化
- AST走査でセクション分割（自前実装）
- 見出しレベル正規化（自前実装）

## 未検討事項

- スキーマ定義での読み書き先指定（`x-storage: markdown` など）
- 書き出し先ファイルの決定方法