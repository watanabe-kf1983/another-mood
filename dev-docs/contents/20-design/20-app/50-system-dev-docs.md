# システム開発ドキュメント

ユーザがシステム設計書を authoring する際に、本ツールが first-class でサポートする artifact 群。各タスクは「artifact 用のスキーマ」「サンプルデータ」「表現テンプレート」の三点セットを blueprint として提供する。

[F (メタドキュメンテーション)](40-meta-documentation.md) との違い: F は catalog から auto-derive する meta-view (ツールが自分自身を説明する用途)、本カテゴリはユーザが authoring した data 上で動く first-party blueprint (ユーザに設計書 authoring の力を授ける用途)。両者は同じ「構造化データ → 自動描画」のメカニズムを共有するが、データの出所 (catalog vs ユーザデータ) と動機が異なる。

## External Design

### S5: 二文書セット (要求仕様書 + 設計書) の目次骨格

単一の showcase プロジェクトから「要求仕様書」「設計書」の二文書を導出する。目的はソフトウェア開発ドキュメントの手本を示すことではなく、Another Mood のソフトウェア開発への応用例を見せること。ただし我流の成果物構成は示さない — 目次の骨格は国際標準 (ISO/IEC/IEEE 29148:2018 / IEEE 1016-2009) から、各 artifact の項目定義は IPA「機能要件の合意形成ガイド」(2010) から借りる。conformance は主張せず "informed by" に留め、docs での謳い方もそう抑える (29148 の full conformance は要求文の特性 5.2.x と Clause 9 の内容要求の網羅義務を伴い、応用例という目的には過剰)。作業言語は日本語で作り切ってから英訳する (W2 の英語化と同じ流れ)。

#### 典拠と借用の分担

| 資料 | 借りるもの | 転載上の制約 |
|---|---|---|
| ISO/IEC/IEEE 29148:2018 | 要求仕様書の目次骨格 (SRS 例示アウトライン 8.5.2 の subset) | 章題の翻案 + "informed by" 表記は確立した慣行で低リスク。本文の逐語転載・アウトライン図の複製は不可 |
| IEEE 1016-2009 | 設計書の章立て (design viewpoint の選抜) | 文書テンプレート非規定のため目次は自作 = 規格想定の使い方。2020 年 Inactive-Reserved (10 年無改訂への管理措置、技術的否定ではない) は docs で言及する |
| IPA 機能要件の合意形成ガイド | 各 artifact の項目定義 (画面 5 成果物 / エンティティ一覧・定義 / CRUD 図 等) | 複製許諾は目的限定付きで翻案禁止条項あり。項目名・構成をアイデアとして借り、定義文は自分の言葉で再設計し、出典を明記する |
| Volere | atomic requirement のレコード属性 (fit criterion / rationale / 優先度 等) | 27 節テンプレートのツール同梱・再配布は要許諾 (redistribution license の明記あり)。属性名 subset + attribution に留める |
| OMG ReqIF v1.2 | スキーマ設計原理 (型と値の分離 / 要求実体と文書階層の分離 / 関係自身が型と属性を持つ) | メタモデル概念の利用は自由。仕様文書の転載のみ不可 |

arc42 (CC BY-SA 4.0) は骨格候補として調査したが不採用: アーキテクチャ文書テンプレートで、網羅的な詳細設計 (全画面定義・CRUD・DB 物理) の受け皿が弱く ("relevance 優先、退屈な部品は書くな" が公式ガイダンス)、翻案物への ShareAlike 継承義務も showcase 配布物には負担。

#### 要求仕様書の目次

informed by 29148 の SRS 例示アウトライン (8.5.2)。BRS / StRS の層は 1 章に畳む (29148 自身が NOTE で「StRS と BRS は多くの業界で同一視され、結合してよい」と明記しており、その根拠で圧縮する)。

| 章 | 内容 | ソース形態 | task |
|---|---|---|---|
| 1. はじめに | 目的 / スコープ / 製品概観 (位置づけ・主要機能・利用者特性・制約)。事業背景 (BRS/StRS 相当) もここに畳む | prose | 器 |
| 2. 用語集 | ドメイン用語辞書 (29148 Definitions 対応) | 構造化データ → 生成 | 器 |
| 3. 要求 | 機能要求 (ユースケース単位) / 外部インタフェース要求 / 品質・性能要求 / 設計制約 | 要求レコード群 → 生成 | S3 |
| 4. 検証 | 3 章にパラレルな要求別検証方法一覧 (29148 が「Section 3 の各節にパラレル」と指定。同一レコードからの別ビュー導出がそのまま実装になる) | 3 章と同じレコード → 別ビュー | S6 |
| 5. 付録 | 前提・依存。**背景: 業務モデル (階層 DFD)** | prose + 構造化データ | S2 |

要求レコードの属性 subset (Volere snow card informed): ID / 種別 / 記述 / 理由 (rationale) / 適合基準 (fit criterion) / 優先度 / 関連ユースケース。3 章の編成軸について 29148 は 7 案を例示した上で「万能の最適編成はなく合意で決めよ」としており、翻案は規格の想定内。

#### 設計書の目次

informed by IEEE 1016-2009 の viewpoint 選抜。1016 は文書テンプレートを規定せず、「concern を cover する viewpoint 集合を選び、選定 rationale を SDD に含める」ことを求める規格なので、選抜による目次自作が正しい使い方。

| 章 | viewpoint | artifact | task |
|---|---|---|---|
| 1. はじめに / 設計方針 | (rationale) | viewpoint 選定理由 | 器 |
| 2. コンテキスト | Context | 外部システム関連図 (DFD レベル 0 と同一データの別描画) | S2 |
| 3. 機能構成 | Composition | 機能一覧 (ユースケースから導出) | S3 |
| 4. データ設計 | Information | ER 図 / エンティティ一覧・定義 / CRUD マトリクス | S3 (S1 の 2 図が接続) |
| 5. 画面設計 | Interface + State dynamics | 画面一覧 / 画面遷移図 / 画面定義 | S4 |

Interaction / Algorithm 等の残 viewpoint は今回の目次に入れない。API 仕様・シーケンス図など将来の Candidates が埋める位置として空けてある。

DFD と CRUD マトリクスは 1016 に明示の viewpoint が無い (DFD の語は 1016 本文に不在で、構造化分析系の記法は Context / Composition に吸収されている。CRUD は Composition × Information の交差)。この創作的マッピングは docs で正直に注記する。

#### 背景: DFD の配置 — 要求仕様書の付録

DFD は業務分析の成果物で、29148 の層構造では BRS/StRS (事業・ステークホルダ要求) の領分。SRS ベースの本文ではなく、畳み込んだ層の背景資料として付録に置く。Volere も業務コンテキスト (§6 The Scope of the Work) を要求文書側に置いており、要求側配置は国際的にも通例。設計書 2 章 (Context) はレベル 0 と同一データを外部システム関連図として別描画する — 同じレコードが二文書に現れる、文書間同期の実証を兼ねる。

DFD は本プロジェクトの製品動機を最もよく体現する artifact でもある。DFD の本質はレベル分割 (コンテキスト図 = レベル 0 → 下位分解) と、親プロセスの入出力フローと子図の入出力が一致するバランシング制約にあり、手描きの図でこの階層整合を維持するコストが DFD を実務から廃れさせた。構造化データ + レベル別自動描画 + ビルド時整合性検査は、この維持コストへの直接の回答になる。

#### 背景: 骨格と項目定義の分担理由 (IPA ローカル性の判定)

IPA ガイドは文書の章立てを提示しない。「工程成果物 ⊂ 設計書」という関係モデルだけを示し、束ね方は各社標準に委ねると明記している (6 領域 × 27 種の工程成果物カタログ + 構成要素の項目定義、という構造)。したがって「IPA から目次を借りる」選択肢はそもそも無く、目次は国際標準・項目定義は IPA という分担はガイド自身の想定用途に沿う。IPA の日本ローカル性は、発注者/開発者の二者モデルや帳票の詳細慣習 (社印・全角/半角文字種・編集フォーマット) といったプロセス前提・詳細度の水準にあり、項目定義そのもの (画面・データモデル・CRUD) は可搬で、採用記法も国際標準 (IDEF1X / BPMN / ユースケース記述) と整合する。帳票・バッチの二領域を今回の範囲外とした理由はローカル性ではなく (存在自体は普遍)、二文書テーゼの実証に必須でなく題材規模に対して過剰なため。Candidates に残す。

#### 29148 の購入判定

不要。目次骨格・規範内容 9.6.1–9.6.20 の項目名・conformance 条項の枠組みは、無料の正規プレビュー (iTeh preview PDF) と二次文献で確定できた。規範本文の詳細 (各節の shall/should 内容) が要るのは conformance を名乗る場合のみで、"informed by" 方針では不要。

#### showcase の形と進め方

- 文書別に blueprint を分けず、単一の showcase プロジェクトから二文書を導出する。CRUD マトリクスやトレーサビリティ (要求 ↔ 設計) は文書をまたいで同じレコードを参照する成果物で、分割すると「単一ソースから同期した文書群」という製品テーゼの実証が立たない
- S2-S4 (+S6) は決まった目次に artifact を埋める増分として実装し、独立に出荷できる。最初に着手する task が showcase プロジェクトの器 (マニフェスト + 二文書の prose 骨格 + 用語集) を敷設する
- artifact ごとに「メタモデル調査 → schema + showcase 例 → view / テンプレート」で積む

#### 情報源

- IPA 機能要件の合意形成ガイド (全 7 分冊 PDF): <https://www.ipa.go.jp/archive/digital/iot-en-ci/jyouryuu/ent03-a.html>
- ISO/IEC/IEEE 29148:2018 正規無料プレビュー (目次全体を含む): <https://standards.iteh.ai/catalog/standards/iso/8cf2bc2b-8b5e-4907-a82a-d1c5676c9e85/iso-iec-ieee-29148-2018>
- IEEE 1016-2009: <https://standards.ieee.org/ieee/1016/4502/>
- Volere Atomic Requirements (公式無料 PDF): <https://www.volere.org/wp-content/uploads/2018/12/06-Atomic-Requirements.pdf>
- OMG ReqIF v1.2 (仕様 PDF 無料): <https://www.omg.org/spec/ReqIF/>
- arc42: <https://arc42.org/overview> (license: <https://arc42.org/license>)

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
- **classDiagram**: `列_with_ドメイン型` ビュー (`from: テーブル` / `flatten: { of: 列, as: 列 }` / `join: { to: 型対応, on: { left: 列.型, right: id }, flatten: { as: 型情報 } }`) でテーブル × 列 × 型対応を結合 → template 側で `groupby('テーブルID')` してクラスに復元
- composition edge: 本題材には親子 entity が無いため出現せず (将来 PoC を拡張するなら確認余地あり)
- association edge: `{% for c in t.列 if c.参照 %}` で `参照` フィールドを持つ列だけ拾う

`列_with_ドメイン型` ビューは flatten + join + nested key (`列.型`) の組合せを 1 本のクエリで実証している (music の `tracks_with_artist` 級の複雑さ)。これが user-land で素直に書けたことで、F4 の built-in 側で同等パターンが必要になっても primitive が足りる見込み。

ユーザ ID 空間にはドット (`.`) が含まれない想定なので、F4 の `mermaid_class_id` フィルタのような alias 化は user-land では不要だった。

#### F4 への含意

- F4 (built-in) の **classDiagram 採用は維持**。catalog 由来の型 (`string` / `integer` / `object`) は括弧無しの論理型なので、S1 で発覚した「括弧入り型 → method 誤判定」問題は起きない
- F4 の `__entity_tree` ビューの蓋然性が S1 で間接的に裏付けられた (flatten + join + nested key を持つクエリが user-land でも素直に書ける)
- ヘッダのみの全体図 (`F4a`) は実機ではかなり「ガラ空き」の見た目になる。実装は予定通り進めつつ、`F4b` 近傍図と並べて読み心地を判断する
- 不足プリミティブは見つからなかった (新規 Jinja2 フィルタ追加なし)

## Proposals

### S2: 階層 DFD

仕様未着手。要求仕様書の付録「背景: 業務モデル」に埋める増分。process (親子参照で階層化) / data store / external entity / flow をモデル化したスキーマから、レベル別の DFD (コンテキスト図 = レベル 0、レベル 1..n) を自動生成する。配置と製品動機の背景は External Design「背景: DFD の配置」参照。

検討項目:

- 階層の構造化: process の親子参照と、レベル別図の切り出し方 (1 レコード集合から n 枚の図を導出)
- バランシング検査: 親プロセスの入出力フローと子図の入出力フローの一致をビルド時に検査できるか。x-ref (FK 整合) の射程を超える制約なので、D 系警告インフラとの接続か、view + テンプレートによる不一致の可視化かを検討する
- 設計書 2 章 (Context) への同一データ別描画 (外部システム関連図)。文書間同期の実証
- Mermaid flowchart 適合性の実機検証。flowchart は「手描き向き」 (構造化データから自動レイアウトしにくい) と評価しており、PlantUML 等への舵切りトリガとして第一候補
- 項目定義の典拠: IPA ガイドに DFD は存在しない (データの流れは業務フロー / バッチ処理フロー / 外部システム関連図に分散)。構造化分析の古典 (DeMarco / Yourdon) と IPA 外部システム関連図の凡例 (ファイル/DB 渡し・メッセージ渡し) を参考に自作する

### S3: CRUD マトリクス + ユースケース構造化

仕様未着手。設計書 4 章 (データ設計) に埋める増分で、要求仕様書 3 章 (要求) のソースになるユースケース entity の構造化もここで行う (Candidates にあった「ユースケース記述」を吸収)。

- CRUD マトリクスは手で書く表ではなく、ユースケース × エンティティの join から導出される view として実装する。要求仕様書側のユースケースと設計書側のエンティティを文書をまたいで参照する、二文書同期の実証の要
- CRUD 図の項目定義 (IPA データモデル編 informed): 行 = ユースケース (または機能)、列 = エンティティ、セル = C/R/U/D (複数可)。行は業務の時系列順、列はイベント系エンティティの作成順に並べる
- ユースケース entity の項目定義は IPA「システム化業務説明」(入出力データ / 基本・例外シナリオ / 事前条件・事後条件) が実質ユースケース記述であり、これを参考にする
- 設計書 3 章 (機能構成) の機能一覧も同じユースケースレコードから導出する

### S4: 画面遷移図 + 画面定義

仕様未着手。設計書 5 章 (画面設計) に埋める増分 (IEEE 1016 では Interface / State dynamics viewpoint、29148 SRS では外部インタフェース要求に対応)。画面 entity + 遷移 entity を構造化し、Mermaid stateDiagram-v2 で遷移図を描く。

検討項目:

- 項目 subset は IPA 画面編の成果物定義 (画面一覧 / 画面遷移 / 画面レイアウト / 画面入出力項目一覧 / 画面アクション明細) から選ぶ。画面レイアウト (描画図) は対象外とし、一覧・遷移・入出力項目・アクションの 4 種を軸にする
- 画面一覧の項目候補: 画面 ID / 画面名 / 分類 / 階層 / 説明 / 関連ユースケース
- 画面入出力項目・アクション明細をどこまで持つか。IPA の識別 ID による画面 ⇔ 項目 ⇔ アクションのクロスリファレンスは文書内同期の実証として有効
- 遷移の条件分岐 (成功時 / 失敗時の遷移先分岐) を stateDiagram の choice node で書き切れるか
- 入口/出口 (`[*]`) の自然な書き方
- 複合 state (画面グループ / モード) の活用可否

S4 は stateDiagram の Mermaid 適合性の実機検証も兼ねる。

## Candidates (未タスク化)

task 化判定は S5 (調査・目次設計) で実施済み。判定結果:

- **要件トレーサビリティ表** → **S6 として task 化**。要求仕様書 4 章「検証」(要求別検証方法一覧) と要求 ↔ 設計 artifact の対応表。29148 が traceability を明示的に求める成果物で、文書横断参照 (x-ref + 表生成テンプレート) の実証としても価値が高い
- **ユースケース記述** → S3 に吸収 (CRUD の行 = ユースケースであり、どのみち構造化が必要)
- **用語集** → 独立 task にせず、要求仕様書 2 章として目次に組込み (最初に着手する task が器と併せて敷設)

下記は引き続き未タスク化。今回の二文書の目次には入れず、空けてある位置 (設計書の Interaction viewpoint 等) に将来埋める:

- **システム構成図 (C4 系)** — Mermaid `C4Context` / `architecture-beta` で描く。後者は v11 でも beta 扱いで機能成熟度未確認。コンポーネント / コンテナ / 関係を構造化データで持つこと自体は可能。アーキテクチャ記述の標準は ISO/IEC/IEEE 42010
- **ユースケース図 / シーケンス図** — ユースケース entity (S3) の図示。Mermaid sequenceDiagram または PlantUML usecase。設計書の Interaction viewpoint を埋める候補
- **API / インタフェース仕様** — エンドポイント / リクエスト / レスポンス / エラーの構造化記述。OpenAPI 風だが本ツール独自スキーマで authoring する形。IEEE 1016 の interface viewpoint に対応
- **帳票定義** — IPA 帳票編 (帳票一覧 / 帳票概要 / 帳票項目説明) を項目典拠に。帳票項目 → 参照先エンティティ・カラムのクロスリファレンスを持ち、文書間同期の題材として筋が良い。帳票の存在自体は日本特有ではないが、二文書テーゼの実証に必須でないため今回は範囲外
- **バッチ処理定義** — IPA バッチ編 (バッチ処理一覧 / バッチ処理フロー / バッチ処理定義) を項目典拠に。処理サイクル / 起動方式 / 再処理方式などの項目定義を持つ

### 順序の見立て

S5 (目次設計) 完了。S2-S4 は決まった目次に埋める増分として独立に着手でき、最初に着手する task が showcase プロジェクトの器 (マニフェスト + 二文書の prose 骨格 + 用語集) を敷設する。S6 (トレーサビリティ表) は要求レコード (S3) が揃ってから。次いで上記候補。
