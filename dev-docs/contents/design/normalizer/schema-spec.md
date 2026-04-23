# Schema Specification

スキーマ定義の仕様。データ構造の検証と正規化のルールを定義する。

## 基本方針

JSON Schema (draft 2020-12) のサブセットを採用する。サポートするキーワードを SchemaSchema（内蔵メタスキーマ）で定義し、バリデーションと正規化の両方を制御する。

## ファイル構成

`schemas_dir`（デフォルト: `docs/definition/schemas/`）配下に YAML ファイルとして配置する。スキーマファイルには `schemas` と `references` の2種類のトップレベルキーがある。1ファイルに両方を書いても、別ファイルに分けてもよい。ファイルの分割・統合・リネームはスキーマ名や参照関係に影響しない。

```yaml
# {schemas_dir}/entities.yaml — ファイル名は整理用
schemas:
  users:
    type: object
    additionalProperties:        # ← 辞書パターンのシグナル
      type: object
      properties:
        name: { type: string }
        email: { type: string }
      required: [name]
  orders:
    type: object
    additionalProperties:
      type: object
      properties:
        title: { type: string }
        customer:
          type: string           # ← users への参照（references で定義）

references:
  - from: orders.customer
    to: users
```

### トップレベルキーの役割

- `schemas`: キー名がスキーマ名、値がそのスキーマの JSON Schema 定義
- `references`: 参照整合性制約の配列（詳細は後述）

この構造は SchemaSchema（内蔵メタスキーマ）によって検証される。`schemas` は `additionalProperties` パターンであり、Normalizer の辞書→配列変換の対象となる。

## サポートする JSON Schema サブセット

### プロジェクトが解釈するキーワード（構造定義）

正規化ロジックが解釈し、辞書→配列変換に関与するキーワード:

- `type` — 値の型を指定
- `properties` — 固定構造のオブジェクト定義
- `additionalProperties` — 辞書パターンのシグナル
- `items` — 配列要素のスキーマ

**`type` の制約**: 単一の型のみサポートする。`object`, `array`, `string`, `number`, `integer`, `boolean` のいずれか。JSON Schema が許す配列形式（例: `type: [string, "null"]`）や `"null"` 型は禁止する。

TBD 値は型の中ではなく、データ側で `remarks` フィールド等のテキスト注記として表現する。

**排他制約**: `properties` と `additionalProperties` は同一オブジェクト内で併用できない。

- `additionalProperties` のみ → 辞書パターン（全キーが同型のエントリ、正規化で配列に変換）
- `properties` のみ → 固定構造（キーと型が事前に決まっているオブジェクト）

### バリデータにスルーパスするキーワード

以下のカテゴリのキーワードはすべてサポートする。プロジェクトは解釈せず、jsonschema ライブラリがそのまま検証に使用する:

- **validation**: `required`, `enum`, `const`, `minimum`, `maximum`, `exclusiveMinimum`, `exclusiveMaximum`, `multipleOf`, `minLength`, `maxLength`, `pattern`, `minItems`, `maxItems`, `uniqueItems`, `minProperties`, `maxProperties` 等
- **meta-data**: `title`, `description`, `default`, `examples`, `deprecated`, `readOnly`, `writeOnly`
- **format-annotation**: `format`
- **content**: `contentMediaType`, `contentEncoding`, `contentSchema`

### サポートしないキーワード

以下は SchemaSchema が拒否する:

- **core** 全般: `$id`, `$schema`, `$ref`, `$defs`, `$anchor`, `$dynamicRef`, `$dynamicAnchor`, `$vocabulary`, `$comment`
- **applicator の合成・条件**: `allOf`, `anyOf`, `oneOf`, `not`, `if`/`then`/`else`
- **applicator のその他**: `patternProperties`, `prefixItems`, `contains`, `propertyNames`, `dependentSchemas`
- **unevaluated**: `unevaluatedProperties`, `unevaluatedItems`

### 背景: なぜサブセットに制限するか

- **`$ref`/`$defs`**: スキーマの再利用が必要な場合、このプロジェクトでは別スキーマに切り出してキー参照する（RDB 的な正規化）。スキーマ内の参照機構は不要
- **合成・条件（`allOf` 等）**: 型のバリエーションはテンプレート記述を複雑にする。バリエーションがあるならスキーマ（= テーブル）を分けるのがこのプロジェクトの方針
- **`$comment`**: YAML のコメント構文（`#`）で代替可能
- **core の残り**: スキーマの識別はトップレベルキー名で行うため、`$id` 等の識別機構は不要

## スキーマ定義

### 正規化後のデータ形状

`additionalProperties` を持つスキーマのデータは、Normalizer により辞書形式から配列形式に変換される。クエリやテンプレートは正規化後の形状を参照する。

```yaml
# {contents_dir}/users.yaml（人間が書く形 — 辞書形式）
tanaka:
  name: 田中太郎
  email: tanaka@example.com
suzuki:
  name: 鈴木花子

# {normalize_contents_dir}/users.yaml（Normalizer が出力 — 配列形式）
items:
  - id: tanaka
    name: 田中太郎
    email: tanaka@example.com
  - id: suzuki
    name: 鈴木花子
```

- 辞書キーが `id` フィールドになる
- 入れ子の `additionalProperties` も再帰的に変換される

正規化ルールの詳細は [normalizer.md](../../internal/components/normalizer.md) を参照。

### コンポジション vs 集約

YAML はツリー構造を持てるため、1:N の子オブジェクトを必ずしも別スキーマに切り出す必要はない。判断基準は「親を消したら子も消えるか」:

- **コンポジション**（消える）→ ネスト。入れ子の `additionalProperties` も正規化される
- **集約**（消えない）→ 別スキーマ + キー参照（references で定義）

```yaml
# コンポジション: 画面の中のボタンは画面と一体
user-screen:
  title: ユーザー画面
  buttons:
    save:
      label: 保存
      action: save
    cancel:
      label: キャンセル
      action: cancel

# 集約: 注文が参照するユーザーは独立して存在
order-001:
  title: 注文A
  customer: tanaka       # 別スキーマ（users）へのキー参照
```

コンポジションの関係にあるオブジェクトは FK として被参照されない。したがって references の参照先はトップレベルスキーマのみで十分。

## エラー報告

スキーマ検証に失敗した場合、エラーメッセージには**ファイル名と行番号**を含める。

```
docs/contents/users.yaml:12: 'email' is a required property
docs/contents/orders.yaml:5: 'customer' expected string, got integer
```

検証はファイル単位で行うため、エラー箇所は自然に元ファイルの行番号で特定できる。

### 背景: なぜ行番号が必要か

JSON Schema のバリデーションは JSON データモデル（パース後の dict/list）に対して行われるため、通常は行番号情報を持たない。しかし「どのファイルの何行目がおかしいか」が分からないエラーメッセージはユーザ体験として不十分であり、将来の LSP 連携（エディタ上の赤波線表示）にも行番号が必須となる。実装には位置情報を保持する YAML パーサ（例: ruamel.yaml）の採用が必要。

## 参照整合性制約: references

参照関係は JSON Schema に埋め込まず、`references` トップレベルキーとして独立して定義する。参照関係は本質的に二者間の関係であり、片側のスキーマに埋め込むのは不自然なため。Snowflake の宣言的 FK と同じアプローチで、制約は**強制しない**。

```yaml
# {schemas_dir}/references.yaml
references:
  - from: orders.customer
    to: users                # users スキーマの .id（省略形）

  - from: orders.assigned_to
    to: users.name           # users スキーマの .name プロパティ
```

### 構文規則

- `from`: 参照する側。`schema_name.property_name` 形式
- `to`: 参照される側。`schema_name`（.id 省略形）または `schema_name.property_name`
- `to` の省略形 `schema_name` は、`additionalProperties` パターンのスキーマでのみ使用可能（辞書キーから生成される `.id` を参照）
- `type: array` のスキーマを参照する場合はプロパティ名の明示が必須（暗黙の ID がないため）
- **参照先はトップレベルスキーマのみ**。ネストパス（`screens.buttons.save` 等）はサポートしない。コンポジション内の入れ子オブジェクトが被参照される必要が出たら、別スキーマに切り出すべきサイン

### 辞書キーが FK の場合（propertyNames パターン）

```yaml
# {schemas_dir}/references.yaml
references:
  - from: user-roles          # 辞書キー自体が FK（propertyNames）
    to: users
```

```yaml
# {contents_dir}/user-roles.yaml
tanaka:                     # ← users.id への参照
  role: admin
suzuki:                     # ← users.id への参照
  role: member
```

`from` にプロパティ名がない場合、辞書のキー自体が参照であることを示す。

### 実行時の振る舞い

> **未実装** — Phase 8 タスク [D1〜D7](../../../tasks.md)。`references` の宣言は SchemaInspector が読み取り `__definition.references` として下流に流すところまで実装済みだが、FK チェック本体と `--strict` フラグは未配線。

- 通常モード: 参照整合性チェックを行わない（TBD だらけの要件定義フェーズに配慮）
- `--strict` モード: 整合性を検証し**警告**として報告（CI/リリース時に使用）。エラーではない

### この宣言が果たす役割

1. **AI へのヒント**: AI がデータ編集時に「このフィールドには users の id が入るべき」と理解できる
2. **ER 図の自動生成**: references からリレーションを読み取り、Mermaid ER 図を描画
3. **影響分析**: 被参照キーを変更しようとした際に「どこから参照されているか」を逆引きで特定できる
4. **リネーム支援**: references に基づいて参照箇所を列挙し、一括置換の漏れを `--strict` で検証できる
