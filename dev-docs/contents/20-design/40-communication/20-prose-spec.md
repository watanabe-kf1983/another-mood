# Prose

散文（prose）は Markdown で書かれ、パイプラインを横断して固有の前処理を受ける唯一のコンテンツ型 — source が path から id を導き、preprocess が title 導出・リンク正規化・順序付けを行い、generator がフォルダ木をネストする。本章はそのうち **読む順と構造** を扱う: 順序を id にどう符号化するか（External Design）と、その順序を book edition がどうネストするか（Internal Design）。パース段の設計（相対リンクの `node:` 正規化・見出し抽出）は [Markdown Parser Specification](../50-normalizer/30-markdown-parser-spec.md) を参照。

## External Design

### 章順は番号 prefix で表す

prose の並び順はファイル名の **ゼロ埋め・隙間空き番号 prefix** で表す（例 `10-architecture.md`）。ディレクトリにも番号を振り、兄弟のファイルとフォルダを一列に並べる。**id / anchor_path は従来どおりファイルパス由来のまま**（番号込み）。番号は id / URL / ファイル名にのみ現れ、表示タイトル（[first-H1 由来](../50-normalizer/30-markdown-parser-spec.md#リンク正規化) の `title`）には出ない。フォルダの `index` は番号を振らず、テンプレートが各フォルダの先頭に置く。順序を effect にする機構は [book edition のフォルダネスト](#book-edition-のフォルダネスト)。

#### 背景: 三すくみ（どれか一つを必ず捨てる）

prose の「順序」と「id」を巡って、次の3つは同時に満たせない:

1. **読む順序がファイルシステム上で見える** — 番号をファイル名に入れる必要がある
2. **id が並べ替え・挿入に対して安定**（＝ `node:` リンク・tasks.yaml の x-ref が壊れない）— 順序を id に入れてはいけない
3. **id の一意性・透明性をファイルシステムがタダで担保**（id ＝ パスそのもの、ロスのない導出）

本決定は **2 を捨てる**。理由:

- 散文の章立てはコードの行番号と違い **早期に安定**し、激しく動かない（書き始めが章立てなので骨格が最初に決まる）
- 番号は順序保持のためのものなので **隙間を空けて振れば挿入は renumber 不要**（`10, 20, 30` に `15` を差す）。renumber が要るのは「隙間が尽きる／構造改組」の稀なときだけ
- id 参照の破れは **Generate のリンク解決が検出**する（[未解決参照の扱い](../70-generator/20-anchor-spec.md#未解決参照の扱い)）。相対リンクはエディタ上でも即座に切れが分かり、rename では自動追従される

よって「並べ替えで id が変わる」コストは prose では **小さく・可視**。一方 1 は authoring の最優先事項（`contents/` に日々住むのは author 自身）、3 を捨てると衝突検査を自前で建て直す羽目になるため残す。

#### 背景: 却下した代替案（蒸し返し防止）

- **front-matter で id を宣言**（順序＝ファイル名／同一性＝front-matter）: 3 を保ちつつ 1+2 を得られるが、id から **segment string ＝住所としての意味を抜く**方向で、resolver の lookup 化と宣言 id の一意性検査という機構を要する。prose id は無意味な UUID ではなく **意味ある住所**（[prose の `/`-素通し例外](../70-generator/20-anchor-spec.md#prose-の例外)）なので、住所性を残す本決定を採る
- **toc yaml / テンプレートでの順序列挙**: リンクの有無に関わらず、**ファイルを rename するたびに spine 側の記帳を無条件に強制**する第二の編集箇所を新設してしまう
- **番号を id から剥がす**: ファイルシステムがタダでくれる一意性・透明性を失い、自前の重複検査が要る（`01-foo` と `02-foo` が同じ id に潰れる衝突をファイルシステムが防げなくなる）
- **key チャネル**（安定ハンドルを id とは別に持つ）: 上記のとおり churn が稀かつ検出可能なので **YAGNI**。加算的な機構なので、実際に痛くなってから独立タスクで足せる（後入れでも手戻りしない）

## Internal Design

### book edition のフォルダネスト

book edition（全 inline）で prose のフォルダ親子をネストさせる仕組みは、[分割ルール](../70-generator/40-paging-spec.md#分割ルール) の two-loop（`| link` + `{% mood_view %}`）と `under_heading` を、フォルダ木へ一般化したもの。各 prose レコードは id 由来の `order_key`（folder-preorder ソートキー）と `depth`（見出しレベル）を持ち、ルートテンプレ（`definition/templates/index.md`）が `order_key` でソートし `depth` に応じて `under_heading` で包む。両フィールドは id のみの純導出なので prose の preprocess（`prose.py` の `_outline_position` が正本）で供給し、ソートはファイル単位で行えないため collection の揃うテンプレ側に置く。`order_key` は暫定のアルファベット id でも番号付き id でも folder-preorder を与えるので、[番号 prefix](#章順は番号-prefix-で表す) を振ればテンプレ無改修で読む順が effect になる。
