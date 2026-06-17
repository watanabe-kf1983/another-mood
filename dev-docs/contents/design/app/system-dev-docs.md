# システム開発ドキュメント

ユーザがシステム設計書を authoring する際に、本ツールが first-class でサポートする artifact 群。各タスクは「artifact 用のスキーマ」「サンプルデータ」「表現テンプレート」の三点セットを blueprint として提供する。

[F (メタドキュメンテーション)](meta-documentation.md) との違い: F は catalog から auto-derive する meta-view (ツールが自分自身を説明する用途)、本カテゴリはユーザが authoring した data 上で動く first-party blueprint (ユーザに設計書 authoring の力を授ける用途)。両者は同じ「構造化データ → 自動描画」のメカニズムを共有するが、データの出所 (catalog vs ユーザデータ) と動機が異なる。

## External Design

### S1: テーブル定義 → 2 種類のスキーマ図 (showcase/japanese-table-design)

`showcase/japanese-table-design` がユーザ-land の参照実装。題材は小規模書店の蔵書管理 (5 テーブル / 4 FK)。スキーマ・データ・description・出力ファイルパスのすべての日本語識別子を運用している。

#### 1 つの source data から 2 つの artifact

S1 は 1 つのテーブル定義データから 2 つの図を生成する:

| Artifact | レイヤ | Mermaid 記法 | 型 |
|---|---|---|---|
| **テーブル設計図 (ER 図)** | データストア物理層 (DDL) | `erDiagram` | `VARCHAR(16)` / `INTEGER` / `DATE` |
| **ドメインモデル図 (クラス図)** | アプリケーション論理層 | `classDiagram` | `string` / `integer` / `date` |

両者は同じ `テーブル` entity を別レイヤから見たもの。橋渡しはユーザ-authored の `型対応` entity が担う (ORM の type mapping 相当)。

```yaml
# contents/型対応.yaml (一部)
型対応:
  "VARCHAR(16)":
    ドメイン型: string
    Python型: str
  INTEGER:
    ドメイン型: integer
    Python型: int
  DATE:
    ドメイン型: date
    Python型: datetime.date
```

スキーマ側では `列.型` に `x-ref: { entity: 型対応 }` を付けて build-time 整合性検査を有効化。

#### 背景: なぜ 2 図を分けるか

「ER 図」を 1 つの notation で語ろうとすると notation 選定で矛盾する:

- **classDiagram** は OO/UML の表現力 (composition / association の区別、`name : type` 形式の属性) を持つが、`(` を含む属性行をメソッドと解釈するヒューリスティックがあり SQL 型 (`VARCHAR(N)`) と衝突する
- **erDiagram** は relational schema の母国語 (PK/FK/UK マーカー、crow's-foot カーディナリティ、`型 名前` の attribute 表) を持つが、composition と association を区別しない (両者をリレーションに潰す)

両者は実は **異なる artifact の母国語** で、無理に競合させず両用するのが整理になる。F4 (built-in メタドキュメンテーション) の方は catalog 型 (`string` / `integer` / `object`) が括弧無しの論理型なので classDiagram の attribute 表記とは整合する — F4 が classDiagram 採用、S1 のテーブル設計図が erDiagram 採用、で notation の責任分割が綺麗に立つ。

#### Mermaid Unicode 制約の実機検証結果

PoC で Mermaid v11 (CDN 経由、Chromium ヘッドレス + Noto CJK) に対して実機確認した結果:

| 位置 | 形式 | 結果 |
|---|---|---|
| classDiagram class 名 | `` class `日本語名` `` (backtick 形式) | OK |
| classDiagram edge ラベル | `` `A` --> `B` : 日本語ラベル `` (unquoted) | OK |
| classDiagram attribute 名 | `日本語名 : 型` (colon 形式) | OK |
| classDiagram attribute 型に括弧 | `日本語名 : VARCHAR(16)` | **NG (メソッドと誤判定され class ボックスが上下分割)** |
| erDiagram entity 名 | `"日本語名" { ... }` (double-quoted) | OK |
| erDiagram attribute 名 | `VARCHAR(16) 日本語属性名 PK` | OK (公式 docs に明文化なし、実機で確認) |
| erDiagram 型表記 | `VARCHAR(16)` `VARCHAR(255)` | OK (括弧入り) |
| erDiagram relationship label | `"A" }o--|| "B" : "日本語ラベル"` | OK |
| erDiagram キー指定 (PK/FK/UK) | ASCII のみ | docs に明記: Unicode 非対応 |
| 日本語 entity ID を含む出力ファイルパス | `__entity_defs/テーブル.md` 等 | OK (mood build 通過) |

#### user-accessible primitive のみで 2 図が描けるか

`showcase/japanese-table-design/definition/templates/index.md` を Jinja2 の素の機能と既存組み込みフィルタのみで実装できた。新規 Jinja2 フィルタも新規 DSL 機能も不要。

- **erDiagram**: `{% for t in テーブル %}` でそのまま展開
- **classDiagram**: `列_with_ドメイン型` クエリ (`from: テーブル` / `flatten: { of: 列, as: 列 }` / `join: { to: 型対応, on: { left: 列.型, right: id }, flatten: { as: 型情報 } }`) でテーブル × 列 × 型対応を結合 → template 側で `groupby('テーブルID')` してクラスに復元
- composition edge: 本題材には親子 entity が無いため出現せず (将来 PoC を拡張するなら確認余地あり)
- association edge: `{% for c in t.列 if c.参照 %}` で `参照` フィールドを持つ列だけ拾う

`列_with_ドメイン型` クエリは flatten + join + nested key (`列.型`) の組合せを 1 クエリで実証している (music の `tracks_with_artist` 級の複雑さ)。これが user-land で素直に書けたことで、F4 の built-in 側で同等パターンが必要になっても primitive が足りる見込み。

ユーザ ID 空間にはドット (`.`) が含まれない想定なので、F4 の `mermaid_class_id` フィルタのような alias 化は user-land では不要だった。

#### F4 への含意

- F4 (built-in) の **classDiagram 採用は維持**。catalog 由来の型 (`string` / `integer` / `object`) は括弧無しの論理型なので、S1 で発覚した「括弧入り型 → method 誤判定」問題は起きない
- F4 の `__entity_tree` クエリの蓋然性が S1 で間接的に裏付けられた (flatten + join + nested key を持つクエリが user-land でも素直に書ける)
- ヘッダのみの全体図 (`F4a`) は実機ではかなり「ガラ空き」の見た目になる。実装は予定通り進めつつ、`F4b` 近傍図と並べて読み心地を判断する
- 不足プリミティブは見つからなかった (新規 Jinja2 フィルタ追加なし)

## Proposals

### S2: DFD (Data Flow Diagram)

仕様未着手。process / data store / external entity / flow をモデル化したスキーマからデータフロー図を描く。Mermaid flowchart で表現できるかは S1 の Mermaid 適合性判断と並べて検討する。flowchart は「手描き向き」 (構造化データから自動レイアウトしにくい) と評価しており、PlantUML 等への舵切りトリガとして第一候補。

### S3: CRUD マトリクス

仕様未着手。ユースケース × エンティティの操作 (C/R/U/D) を行列形式で表す。エンティティ集合は catalog (`__definition.entities`) から取れる。ユースケース集合と CRUD 操作はユーザ-authored data を作る必要があり、ユースケース entity の構造化に踏み込む。S? (ユースケース記述) と連携する可能性が高い。

### S4: 画面遷移図 + 画面定義

仕様未着手。画面 entity と遷移 entity で構造化し、Mermaid stateDiagram-v2 で遷移図を描く。

検討項目:

- 画面定義の項目構成 (画面 ID / 名前 / 役割 / 入力項目 / 出力項目 / バリデーション / 関連ユースケース)
- 遷移の条件分岐 (成功時 / 失敗時の遷移先分岐) を stateDiagram の choice node で書き切れるか
- 入口/出口 (`[*]`) の自然な書き方
- 複合 state (画面グループ / モード) の活用可否

S4 は stateDiagram の Mermaid 適合性の実機検証も兼ねる。

## Candidates (未タスク化)

下記は将来 S5 以降として task 化し得る候補。**設計書全体の目次設計を起点に各 artifact の範囲が決まる** ため、現時点では task 化を保留する。目次自体の検討には [カテゴリ A (Markdown パーサー拡張)](../normalizer/markdown-parser-spec.md) / [カテゴリ B (アンカー・リンク解決)](../generator/generator.md) の完了が前提。

- **システム構成図 (C4 系)** — Mermaid `C4Context` / `architecture-beta` で描く。後者は v11 でも beta 扱いで機能成熟度未確認。コンポーネント / コンテナ / 関係を構造化データで持つこと自体は可能
- **要件トレーサビリティ表** — 要件 ID × {コンポーネント / テスト / 決定} の対応表。要件と他 artifact の参照関係を維持する仕組み (x-ref + 表生成テンプレート) で実現可能
- **ユースケース記述 / ユースケース図** — 構造化された usecase + actor + step。S3 (CRUD) の前段としても機能。図示は Mermaid sequenceDiagram または PlantUML usecase
- **用語集 / データ定義書** — ドメイン用語の辞書、entity の別名 / 型補足 / 帰属モジュール。entity に metadata を載せて生成可能
- **API / インタフェース仕様** — エンドポイント / リクエスト / レスポンス / エラーの構造化記述。OpenAPI 風だが本ツール独自スキーマで authoring する形

### 順序の見立て

設計書の目次 (= 章立て) を author が prose で書く能力が前提なので、A/B の完了 → 目次 prose のドラフト → 個別 artifact (上記候補) を埋める、の順。先に個別 artifact だけ作ると目次との整合が後出しで surface して書き直しになりやすい。
