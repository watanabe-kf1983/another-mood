# Document Generator

## 内蔵ルートテンプレート

Generator はユーザの `index.md` テンプレートを直接エントリポイントとせず、内蔵のルートテンプレートを起点とする。ルートテンプレートは以下の 3 セクションを持つ:

1. **エラー** — `__build_report` にエラーがあればビルドレポートテンプレート（内蔵）でレンダリング
2. **メタドキュメンテーション** — 内蔵テンプレートでスキーマ・クエリを可視化（[meta-documentation.md](../../external/app/meta-documentation.md) 参照）
3. **ユーザドキュメント** — ユーザの `index.md` テンプレートを呼び出す

これにより、エラー表示・メタドキュメンテーション・ユーザドキュメントがすべて同じテンプレートシステム上で動作する。generator.py にハードコードされたエラーフォーマット処理は不要になる。

## 処理フロー

1. `viewsDir` の *.yaml 読み込み
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
