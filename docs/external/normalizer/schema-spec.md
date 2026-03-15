# Schema Specification

スキーマ定義の仕様。データ構造の検証と正規化のルールを定義する。

## 基本方針

JSON Schema をそのまま採用する。独自スキーマ形式は設計しない。

## スキーマ定義

### ファイル構成

`model/schema/` 配下に YAML ファイルとして配置する。1ファイルに複数スキーマを定義可能で、**トップレベルキーがスキーマ名**となる（ファイル名はスキーマ名に影響しない）。

```yaml
# schema/entities.yaml — ファイル名は整理用、スキーマ名はトップレベルキー
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
        type: string           # ← users への参照（references.yaml で定義）
```

ファイルの分割・統合・リネームはスキーマ名や参照関係に影響しない。

### 正規化ルール

`additionalProperties` がオブジェクトスキーマの場合、辞書パターンとして扱い、配列 + id フィールドに正規化する:

- `additionalProperties` がオブジェクトスキーマ → 辞書パターン。`properties` に明示されたキーはそのまま残し、それ以外のキーを配列 + id フィールドに変換
- `properties` のみ → 固定構造のオブジェクト、そのまま
- 入れ子の `additionalProperties` も再帰的に正規化する

```yaml
# data/users.yaml（人間が書く形 — 辞書形式）
version: "1.0"
tanaka:
  name: 田中太郎
  email: tanaka@example.com
suzuki:
  name: 鈴木花子

# output/model/normalized/users.yaml（Normalizer が出力 — 配列形式）
version: "1.0"
items:
  - id: tanaka
    name: 田中太郎
    email: tanaka@example.com
  - id: suzuki
    name: 鈴木花子
```

### コンポジション vs 集約

YAML はツリー構造を持てるため、1:N の子オブジェクトを必ずしも別スキーマに切り出す必要はない。判断基準は「親を消したら子も消えるか」:

- **コンポジション**（消える）→ ネスト。入れ子の `additionalProperties` も正規化される
- **集約**（消えない）→ 別スキーマ + キー参照（references.yaml で定義）

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

コンポジションの関係にあるオブジェクトは FK として被参照されない。したがって references.yaml の参照先はトップレベルスキーマのみで十分。

## 参照整合性: references.yaml

参照関係は JSON Schema に埋め込まず、`schema/references.yaml` に独立して定義する。参照関係は本質的に二者間の関係であり、片側のスキーマに埋め込むのは不自然なため。Snowflake の宣言的 FK と同じアプローチで、制約は**強制しない**。

```yaml
# schema/references.yaml
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
# schema/references.yaml
- from: user-roles          # 辞書キー自体が FK（propertyNames）
  to: users
```

```yaml
# data/user-roles.yaml
tanaka:                     # ← users.id への参照
  role: admin
suzuki:                     # ← users.id への参照
  role: member
```

`from` にプロパティ名がない場合、辞書のキー自体が参照であることを示す。

### 実行時の振る舞い

- 通常モード: 参照整合性チェックを行わない（TBD だらけの要件定義フェーズに配慮）
- `--strict` モード: 整合性を検証し**警告**として報告（CI/リリース時に使用）。エラーではない

### この宣言が果たす役割

1. **AI へのヒント**: AI がデータ編集時に「このフィールドには users の id が入るべき」と理解できる
2. **ER 図の自動生成**: references.yaml からリレーションを読み取り、Mermaid ER 図を描画
3. **影響分析**: 被参照キーを変更しようとした際に「どこから参照されているか」を逆引きで特定できる
4. **リネーム支援**: references.yaml に基づいて参照箇所を列挙し、一括置換の漏れを `--strict` で検証できる
