# CLI 仕様

Another Mood のコマンドラインインターフェース。

## 処理対象ディレクトリ

全コマンドは第一位置パラメータ `<projectDir>` で処理対象ディレクトリを受け取る。

- `<projectDir>` は CWD からの相対パスで指定する（典型的には `.`）
- CWD 配下のパスのみ許可。CWD 外のパス（`../other-repo/docs` 等）はエラーとする
- 入力パスの解決: 設定の入力系デフォルトパスは `<projectDir>` を基準に解決される（[config-spec.md](config-spec.md) 参照）
- 出力パスの解決: 出力は CWD 基準で `.another-mood/<projectDir>/` 配下に配置される（[config-spec.md](config-spec.md) 参照）

## コマンド一覧

### mood init

プロジェクトの初期化。`<projectDir>` に [project-structure.md](project-structure.md) に準拠したディレクトリ構成とサンプルデータを生成する。

```
mood init <projectDir> [--template <name>]
```

- `--template <name>` で同梱テンプレートを選択する。省略時は `starter`
- 利用可能なテンプレート: `showcase/` 直下の各サブディレクトリ名（例: `starter`, `ecommerce`）
- 不正なテンプレート名を渡した場合はエラーメッセージ（利用可能テンプレート一覧を含む）を表示し exit code 1 で終了
- 既存ファイルがある場合は上書きしない（競合時は警告を表示してスキップ）

MCP の init ツール（[mcp-design.md](mcp-design.md)）は同じテンプレート群を扱う。AI が showcase の具体例を体験する経路を CLI と MCP で揃えるため、テンプレート列挙ロジックは scaffold コンポーネントに集約する。

### mood watch

常駐モード。ファイル変更を監視して自動再処理し、Hugo server でプレビューを配信する。

```
mood watch <projectDir> [--host <addr>] [--port <port>]
```

`--host` は preview server の bind アドレス。デフォルト `127.0.0.1`（localhost のみ）。`0.0.0.0` 等を指定すると LAN 上の他端末から preview server に接続可能になる。preview server には認証がないため、信頼できるネットワーク内でのみ使うこと。

想定ユースケース: 要件定義 / 設計会議で 1 人がソースを更新、出席者全員が即座にブラウザでドキュメントを参照する collaborative authoring。同一 LAN 上のメンバーに対して `--host 0.0.0.0` で開く。

複数ディレクトリを同時に監視したい場合は、複数プロセスで起動する。出力先は `<projectDir>` ごとに自動分離されるため衝突しない。ただしポートが競合するため、2つ目以降は `--port` で別ポートを指定する必要がある。

### mood build

一括ビルド。全段を実行し、静的ファイルを生成する。

```
mood build <projectDir>
```

用途:

- CI やリリース
- コーディングエージェントとの協業。エージェントがファイルを編集した後に `mood build` を実行し、exit code で成否を判定する。ブラウザ側は VS Code Live Server 等で `render/` ディレクトリを常時配信し、人がリロードで確認する。`mood watch` の Watcher はエージェントがファイルを書き換える場合は不要であり、同期的な `mood build` の方がエージェントのワークフローに合う。
