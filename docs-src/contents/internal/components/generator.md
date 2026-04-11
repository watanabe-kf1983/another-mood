# Document Generator

## 内蔵ルートテンプレート

Generator はユーザの `index.md` テンプレートを直接エントリポイントとせず、内蔵のルートテンプレートを起点とする。ルートテンプレートは以下の 2 セクションを持つ:

1. **メタドキュメンテーション** — 内蔵テンプレートでスキーマ・クエリを可視化（[meta-documentation.md](../../external/app/meta-documentation.md) 参照）
2. **ユーザドキュメント** — ユーザの `index.md` テンプレートを呼び出す

これにより、メタドキュメンテーション・ユーザドキュメントが同じテンプレートシステム上で動作する。

エラー時の出力差し替えは Generator の責務ではなく、後段の Reconcile ステージ（後述）が担う。Generator 自身は views を Markdown に変換する純粋な責務に集中する。テンプレートのレンダリング中に発生した例外は `error_propagation` が捕捉して reports/ に書き出し、Reconcile がそれを見てエラーページに差し替える。

## 処理フロー

1. `compose_dir` の *.yaml 読み込み
2. `profilesFile` の paginate 設定を読み込み
3. 内蔵ルートテンプレートからレンダリング開始
   - {% section %} が paginate を参照し、分割 or インライン判定
   - link_md フィルタがアンカー ID を解決しリンク生成
4. Markdown 内の toc:id リンクを解決
5. `outDir`/{profile_name}/ にファイル書き出し

## リンク解決

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

### prose body 内のリンク解決

Markdown データソースの body には、Normalizer がソース内の相対リンクを `toc:` 記法に変換済みのリンクが含まれる（[markdown-parser-spec.md](../external/normalizer/markdown-parser-spec.md) 参照）。Generator はこれを上記と同じ仕組みで解決する。追加のリンク解決ロジックは不要。

## パーシャルテンプレートとエスケープ

パーシャル単位で出力フォーマットが決まり、拡張子でエスケープモードを判定する:

| 拡張子 | エスケープモード |
|---|---|
| `.md` | Markdown エスケープ |
| `.mermaid` | Mermaid エスケープ |

## Technical Stack

### テンプレートエンジン

Jinja2 を採用する:

- **autoescape**: パーシャル単位のエスケープモード切り替えにフィット
- **フィルタの充実**: `map`, `select`, `reject`, `groupby` 等のフィルタが標準で利用可能
- **カスタムタグ（Extension）**: `{% section %}` の実装に使用

## Reconcile

Reconcile は Generator の直後に位置するステージで、「Generator の出力（あるべき姿）」と「上流から伝播してきた `BuildReport`（実際に何が起きたか）」を突き合わせ、ユーザに見せる最終出力を確定する役割を持つ。

- エラー無し: Generator の出力をそのまま `reconcile_dir` に通す（pass-through）
- エラー有り: Generator の出力を破棄し、`__build_report` テンプレートでエラーページをレンダリングして `reconcile_dir` に書き出す

この分離により以下が成立する:

- Generator は「views を Markdown に変換する」純粋な責務に集中できる（エラー時の出力差し替えロジックを持たない）
- 下流の Render / publish_stage / build_report_stage はすべて `reconcile_dir`（= Reconcile の出力）の単一視点を持てばよく、エラー時と正常時の分岐を知らなくてよい
- Reconcile が pipeline の意味的な末端 = ビルドの canonical な状態を表すため、`build_report_stage` が見るべき reports も Reconcile の出力に含まれる reports/ となる

### 命名について

「reconcile（突き合わせる）」は本リポジトリ独自の語ではなく一般的な英単語だが、ドキュメントビルダーの文脈では珍しい語であり、馴染みのある語が引き起こす意味の取り違えを避ける狙いで採用した。読み手はこの定義に立ち戻ることで、Reconcile ステージの責務を一意に把握できる。
