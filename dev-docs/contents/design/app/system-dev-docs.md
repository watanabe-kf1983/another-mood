# システム開発ドキュメント

ユーザがシステム設計書を authoring する際に、本ツールが first-class でサポートする artifact 群。各タスクは「artifact 用のスキーマ」「サンプルデータ」「表現テンプレート」の三点セットを blueprint として提供する。

[F (メタドキュメンテーション)](meta-documentation.md) との違い: F は catalog から auto-derive する meta-view (ツールが自分自身を説明する用途)、本カテゴリはユーザが authoring した data 上で動く first-party blueprint (ユーザに設計書 authoring の力を授ける用途)。両者は同じ「構造化データ → 自動描画」のメカニズムを共有するが、データの出所 (catalog vs ユーザデータ) と動機が異なる。

## Proposals

### S1: テーブル定義 → ERD

[meta-documentation.md「ER 図 (S1 + F4a-F4c)」](meta-documentation.md#er-図-s1--f4a-f4c) を参照。本タスクは built-in メタドキュメンテーションの F4 と一体で設計しており、共通の決定 (Mermaid classDiagram 採用 / edge ラベル = FK 属性名 / カーディナリティ非表示など) は同節に集約してある。

S1 は **user-land で ERD が描けることを実証する PoC** であり、F4a-c はそのパターンを built-in に輸入する位置づけ。S1 の追加成果として、Mermaid classDiagram の Unicode 制約 (日本語 class 名 / 属性名 / edge ラベル) の実機検証も含まれる。

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
