# システム開発ドキュメント

ユーザがシステム設計書を authoring する際に、本ツールが first-class でサポートする blueprint 群。「artifact 用のスキーマ」「サンプルデータ」「表現テンプレート」の三点セットを showcase として提供する。

[F (メタドキュメンテーション)](../75-meta-documentation/10-database-information.md) との違い: F はカタログから auto-derive する meta-view (ツールが自分自身を説明する用途)、本カテゴリはユーザが authoring した data 上で動く first-party blueprint (ユーザに設計書 authoring の力を授ける用途)。両者は同じ「構造化データ → 自動描画」のメカニズムを共有するが、データの出所 (カタログ vs ユーザデータ) と動機が異なる。

## External Design

### showcase/system-dev-docs-ja / -en: 要求仕様書と設計書の二文書

単一の sbdb プロジェクトから要求仕様書と設計書 (en では SRS / SDD) を導出する showcase。題材は小規模書店の在庫管理システム (書籍マスタ / 入荷 / 販売 / 棚卸)。ja を作り切ってから複製・英訳した二つの別プロジェクトで、構造は同一。

守るもの:

- **二文書を一つの sbdb プロジェクトから導出する**。文書別に blueprint を分けると、CRUD マトリクスやトレーサビリティのように文書をまたいで同じレコードを参照する成果物が作れず、「単一ソースから同期した文書群」という製品テーゼの実証が立たない
- **showcase は内容ではなく機構の見本**。作られるべき文書とその粒度は開発プロジェクト固有で標準化もテンプレ化もできない (だからこそ構造を柔軟に定義できるツールが要る)。schema はそのまま流用されるものではなく「読んで自分の構造に書き換えるための見本」であり、価値は読みやすさと改変しやすさにある。description の典拠注記と英名はその改変の手がかり
- **標準への conformance は主張せず "informed by" に留める**。docs での謳い方もそう抑える (29148 の full conformance は要求文の特性 5.2.x と Clause 9 の網羅義務を伴い、応用例という目的には過剰)。よりどころは目次ではなくモデルに置き、項目の典拠は成果物の系統ごとに一つ (設計書側は IPA ガイド、要求仕様書側は 29148 + Volere)。資料ごとに借りるものと転載上の制約 (IPA の翻案禁止条項、Volere の再配布許諾) は[典拠と借用の分担](../../90-appendix/20-design/80-showcase/10-system-dev-docs.md#典拠と借用の分担)
- **参照の向きは下流 (設計書のソース) → 上流 (要求仕様書のソース) のみ**で、上流のデータは下流を知らずに閉じる。業務層はさらに上にあり、他のどの層も知らない

モデル (章 → ソース、エンティティ → 登場章、各層の規則とその意図) の正本は schema.yaml の冒頭・節コメントと description、テンプレートのコメント。図は `mood build showcase/system-dev-docs-ja` の `__db/__defs/entities` (ER メタビュー) で読める。ja / en の対応は ja の schema.yaml が description 末尾に付記する英名で取る (書式は schema.yaml 冒頭のコメント)。

設計に至った過程 (調査の帰結、層の対応、章立てと英語版の判断、将来の章の候補、showcase で表面化したツール側の検討事項) は[背景](../../90-appendix/20-design/80-showcase/10-system-dev-docs.md)。
