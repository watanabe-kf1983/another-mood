# CLI 仕様

reqs-builder のコマンドラインインターフェース。

> **Note**: コマンド名（`reqs`）は仮称。ツール名とともに後日決定。

## コマンド一覧

### reqs dev

常駐モード。ファイル変更を監視して自動再処理し、Hugo server でプレビューを配信する。

```
reqs dev [--port <port>]
```

### reqs build

一括ビルド。全段を実行し、静的ファイルを生成する。CI やリリース用途を想定。

```
reqs build
```

### reqs normalize / compose / generate

各ステージの単体実行。

```
reqs normalize
reqs compose
reqs generate
```
