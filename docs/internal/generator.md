# Document Generator

## 処理フロー

1. output/model/views/*.yaml 読み込み
2. profiles.yaml の paginate 設定を読み込み
3. index テンプレートからレンダリング開始
   - {% section %} が paginate を参照し、分割 or インライン判定
   - link_md フィルタがアンカー ID を解決しリンク生成
4. Markdown 内の toc:id リンクを解決
5. output/documents/{profile_name}/ にファイル書き出し

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

### 図表記

- 基本: Mermaid（ER図、シーケンス図、フローチャート等）
- Mermaid 非対応の図（ユースケース図等）は代替記法で対応
- 将来: PlantUML 対応を検討（Java 依存のため優先度低）

### 現行 TypeScript 実装（参照実装）

- テンプレート: LiquidJS
- YAML 処理: js-yaml
- ファイル監視: chokidar

```
src/
  commands/
    generate.ts         # reqs-builder generate
  core/
    toc.ts              # toc定義の読み込み・展開
    template-expander.ts # テンプレート展開
```
