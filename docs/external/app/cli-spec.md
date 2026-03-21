# CLI 仕様

reqs-builder のコマンドラインインターフェース。

> **Note**: コマンド名（`reqs`）は仮称。ツール名とともに後日決定。

## 処理対象ディレクトリ

全コマンドは第一位置パラメータ `<projectDir>` で処理対象ディレクトリを受け取る。

- `<projectDir>` は CWD からの相対パスで指定する（典型的には `.`）
- CWD 配下のパスのみ許可。CWD 外のパス（`../other-repo/docs` 等）はエラーとする
- 入力パスの解決: 設定の入力系デフォルトパスは `<projectDir>` を基準に解決される（[config-spec.md](config-spec.md) 参照）
- 出力パスの解決: 出力は CWD 基準で `.reqs-builder/<projectDir>/` 配下に配置される（[config-spec.md](config-spec.md) 参照）

## コマンド一覧

### reqs init

プロジェクトの初期化。`<projectDir>` に [project-structure.md](project-structure.md) に準拠したディレクトリ構成とサンプルデータを生成する。

```
reqs init <projectDir>
```

- 既存ファイルがある場合は上書きしない（競合時は警告を表示してスキップ）

### reqs dev

常駐モード。ファイル変更を監視して自動再処理し、Hugo server でプレビューを配信する。

```
reqs dev <projectDir> [--port <port>]
```

複数ディレクトリを同時に監視したい場合は、複数プロセスで起動する。出力先は `<projectDir>` ごとに自動分離されるため衝突しない。

### reqs build

一括ビルド。全段を実行し、静的ファイルを生成する。CI やリリース用途を想定。

```
reqs build <projectDir>
```

### reqs normalize / compose / generate

各ステージの単体実行。

```
reqs normalize <projectDir>
reqs compose <projectDir>
reqs generate <projectDir>
```
