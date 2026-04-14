# CLI 仕様

another-mood のコマンドラインインターフェース。

## 処理対象ディレクトリ

全コマンドは第一位置パラメータ `<projectDir>` で処理対象ディレクトリを受け取る。

- `<projectDir>` は CWD からの相対パスで指定する（典型的には `.`）
- CWD 配下のパスのみ許可。CWD 外のパス（`../other-repo/docs` 等）はエラーとする
- 入力パスの解決: 設定の入力系デフォルトパスは `<projectDir>` を基準に解決される（[config-spec.md](config-spec.md) 参照）
- 出力パスの解決: 出力は CWD 基準で `.another-mood/<projectDir>/` 配下に配置される（[config-spec.md](config-spec.md) 参照）

## コマンド一覧

### mood init

> **未実装** — Phase 8 タスク [G1](../../../phase8-tasks.md)

プロジェクトの初期化。`<projectDir>` に [project-structure.md](project-structure.md) に準拠したディレクトリ構成とサンプルデータを生成する。

```
mood init <projectDir>
```

- 既存ファイルがある場合は上書きしない（競合時は警告を表示してスキップ）

### mood dev

常駐モード。ファイル変更を監視して自動再処理し、Hugo server でプレビューを配信する。

```
mood dev <projectDir> [--port <port>]
```

複数ディレクトリを同時に監視したい場合は、複数プロセスで起動する。出力先は `<projectDir>` ごとに自動分離されるため衝突しない。ただしポートが競合するため、2つ目以降は `--port` で別ポートを指定する必要がある。

### mood build

一括ビルド。全段を実行し、静的ファイルを生成する。

```
mood build <projectDir>
```

用途:

- CI やリリース
- コーディングエージェントとの協業。エージェントがファイルを編集した後に `mood build` を実行し、exit code で成否を判定する。ブラウザ側は VS Code Live Server 等で `render/` ディレクトリを常時配信し、人がリロードで確認する。`mood dev` の Watcher はエージェントがファイルを書き換える場合は不要であり、同期的な `mood build` の方がエージェントのワークフローに合う。
