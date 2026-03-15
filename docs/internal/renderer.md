# Document Renderer

## 処理フロー

1. Hugo が output/documents/ → output/rendered/ に変換

## Technical Stack

- Hugo (hugo-bin 経由): Go 製シングルバイナリ、高速ビルド、ライブリロード対応
- 将来: AsciiDoc レンダリング環境への差し替えも検討

### 現行 TypeScript 実装（参照実装）

```
src/
  commands/
    dev.ts              # reqs-builder dev (統合起動、Hugo サーバ含む)
resources/
  hugo/
    hugo.toml           # Hugo 設定
    layouts/            # Hugo レイアウト
```
