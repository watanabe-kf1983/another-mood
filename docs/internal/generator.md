# Document Generator

## 処理フロー

1. output/model/views/*.yaml 読み込み
2. profiles.yaml の paginate 設定を読み込み
3. index テンプレートからレンダリング開始
   - {% section %} が paginate を参照し、分割 or インライン判定
   - link_md フィルタがアンカー ID を解決しリンク生成
4. Markdown 内の toc:id リンクを解決
5. output/documents/{profile_name}/ にファイル書き出し

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

## パーシャルテンプレートとエスケープ

パーシャル単位で出力フォーマットが決まり、拡張子でエスケープモードを判定する:

| 拡張子 | エスケープモード |
|---|---|
| `.md` | Markdown エスケープ |
| `.mermaid` | Mermaid エスケープ |

## Technical Stack

### テンプレートエンジン

TypeScript の場合は LiquidJS を採用する:

- **フィルタの充実**: `map`, `uniq`, `where` 等のフィルタが標準で利用可能（Nunjucks にはない）
- **Shopify Liquid 互換**: 広く使われている Shopify テーマの記法と互換性があり、ドキュメントやサンプルが豊富

Python の場合は Jinja2 を採用する:

- **autoescape**: パーシャル単位のエスケープモード切り替えにフィット
