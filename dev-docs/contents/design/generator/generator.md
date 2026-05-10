# Document Generator

## 内蔵ルートテンプレート

Generator はユーザの `index.md` テンプレートを直接エントリポイントとせず、内蔵のルートテンプレートを起点とする。ルートテンプレートは以下の 2 セクションを持つ:

1. **メタドキュメンテーション** — 内蔵テンプレートでスキーマ・クエリを可視化（[meta-documentation.md](../app/meta-documentation.md) 参照）
2. **ユーザドキュメント** — ユーザの `index.md` テンプレートを呼び出す

これにより、メタドキュメンテーション・ユーザドキュメントが同じテンプレートシステム上で動作する。

## パーシャルテンプレートとエスケープ

パーシャル単位で出力フォーマットが決まり、拡張子でエスケープモードを判定する:

| 拡張子 | エスケープモード |
|---|---|
| `.md` | Markdown エスケープ |
| `.mermaid` | Mermaid エスケープ |

## Reconcile

Reconcile は Generator の直後に位置するステージで、「Generator の出力（あるべき姿）」と「上流から伝播してきた `BuildReport`（実際に何が起きたか）」を突き合わせ、ユーザに見せる最終出力を確定する役割を持つ。

- エラー無し: Generator の出力をそのまま `reconcile_dir` に通す（pass-through）
- エラー有り: Generator の出力を破棄し、`__build_failure` テンプレートでエラーページをレンダリングして `reconcile_dir` に書き出す

この分離により以下が成立する:

- Generator は「views を Markdown に変換する」純粋な責務に集中できる（エラー時の出力差し替えロジックを持たない）
- 下流の Render / publish_stage は `reconcile_dir`（= Reconcile の出力）の単一視点を持てばよく、エラー時と正常時の分岐を知らなくてよい

### 命名について

「reconcile（突き合わせる）」は本リポジトリ独自の語ではなく一般的な英単語だが、ドキュメントビルダーの文脈では珍しい語であり、馴染みのある語が引き起こす意味の取り違えを避ける狙いで採用した。読み手はこの定義に立ち戻ることで、Reconcile ステージの責務を一意に把握できる。

## proposal

### リンク解決 (B1-B6)

> **未実装** — Phase 8 タスク [B1〜B6](../../../tasks.md)。アンカーの仕様は [anchor-spec.md](anchor-spec.md) を参照。

views データのラッパーツリーを構築する。各ラッパーオブジェクトは:

- `data`: 元の JSON オブジェクト
- `parent`: 親ラッパー
- `class_name`: クラス名
- `get_page_url()`: 自身が paginate 対象なら自ページパス、でなければ `parent.get_page_url()`

link_md / toc:id によるリンク解決:

1. アンカー ID でツリーを走査し、最初にヒットしたラッパーを返す
2. ヒットしたらキャッシュ（anchor_id → ラッパー）に登録
3. 2回目以降は O(1) で解決
4. ラッパーの `get_page_url()` + フラグメント（`#anchor_id`）でリンク URL を生成

全ノードの事前インデックスは構築しない。リンク対象は主要オブジェクトのごく一部であり、オンデマンド走査 + キャッシュで十分。

#### prose body 内のリンク解決

Markdown データソースの body には、Normalizer がソース内の相対リンクを `toc:` 記法に変換済みのリンクが含まれる（[markdown-parser-spec.md](../normalizer/markdown-parser-spec.md) 参照）。Generator はこれを上記と同じ仕組みで解決する。追加のリンク解決ロジックは不要。

### インラインコードのフェンス長

内蔵テンプレート（`__meta_entity` の attributes 表など）は、`metadata` / `validation` のような任意 Mapping を Markdown テーブルセルに `{{ value | to_yaml(true) }}` でダンプし、結果をインラインコードとして表示している。現在は単一バッククォートで囲んでいるが、値そのものにバッククォートが含まれると CommonMark のフェンスが内側で早期終了してセルが崩れる。

例: 値の中に `` `text/markdown` `` が含まれていると、

```
`always `text/markdown` ...`
```

の 2 番目のバッククォートが終端と解釈され、`text/markdown` がコード表示から外れる。

CommonMark の規定どおり、**値に出てくる連続バッククォートの最長 + 1** の長さでフェンスを動的に決める `code_fence` フィルタを導入してテンプレートから呼ぶ:

- 値にバッククォートを含まない → `` ` `` で囲む
- 1 個含む → `` `` `` で囲む
- 2 連続含む → ` ``` ` で囲む

値の先頭/末尾がバッククォートのときは内側に半角スペースを足す（CommonMark の規定。`` ` ` ` `` のように単独のバッククォートを表示するため）。
