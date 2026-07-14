# 設定システム仕様

## External Design

### 設定の読み込み優先順位

設定は以下の順序でマージされる（後のものが優先）:

1. デフォルト値
2. 設定ファイル（未実装 — [G2](node:/tasks/G/tasks/G2)）
3. 環境変数
4. CLI 引数

## Proposals

### 設定ファイル (G2)

- ファイル名: `another-mood.config.json`
- 配置場所: プロジェクトルート
- 対応フォーマット: JSON

### render.customServer.command (G3)

> **未実装** — Phase 10 タスク [G3](node:/tasks/G/tasks/G3)。

カスタムレンダリングサーバのコマンドを設定すると、Hugo の代わりに使用される。詳細は下表。

### 処理対象ディレクトリの CWD 配下制約 (G8)

> **未実装** — タスク [G8](node:/tasks/G/tasks/G8)。

`<projectDir>` 引数（`project_dir`）が CWD 配下にあることを必須とし、CWD 外を指す場合はエラーで拒否する（相対 `../other-repo/docs`・絶対 `/some/elsewhere/docs` の両方）。`out_dir` / `render_dir` / `tmp_dir`、および入力サブパス（`schema_file` 等）の `RB_*` 上書きは制約しない。制約は build / watch（`ProjectConfig` 経由）にのみ効き、`init` / `apply_blueprint`（プロジェクト作成）は対象外。

#### 背景: なぜ project_dir だけを縛るか

目的はサンドボックス（CWD 外の読み書き禁止）ではなく、**出力配置キーの前提を守ること**。

[project-structure.md](10-project-structure.md) の「出力を `<projectDir>` ごとにサブディレクトリで分離する理由」のとおり、出力は `.another-mood/<projectDir>/` に置き、サブディレクトリ名に「CWD からの相対パス」を使って予測可能性を担保している。このキーは `project_dir` が CWD 配下にあって初めて定義できる。CWD 外の `project_dir` はこのキーを持てず、現状は `_another_mood_root` (`config.py`) が basename にフォールバックして `.another-mood/<basename>/` に着地させる——`/a/proj` と `/b/proj` が衝突する lossy な挙動で、出力先が入力の実在位置を反映しない。G8 はこの綻びを、フォールバックではなくエラーで塞ぐ。

`out_dir` / `render_dir` は「どこに書き出すか」という別の関心で、CWD 外への publish は正当な用途（隣の web root 等）がありうるため縛らない。`tmp_dir` は [G9](node:/tasks/G/tasks/G9) でシステム temp を既定としており、CWD 外が正しい。入力サブパスの `RB_*` 上書きは出力キーの派生に関与せず、この綻びを生まないため縛らない。

#### 背景: なぜ「CWD 外 + 明示 out_dir」を許容しないか

`project_dir` が CWD 外でも `out_dir` を明示すればキーの問題は回避できるが、その逃げ道は設けない。Another Mood ドキュメントプロジェクトは通常リポジトリ内に 0〜n 個置かれるという使い方から、CWD 外指定の需要は薄く、分岐を増やして仕様・実装を複雑にする価値がない。必要になれば後から緩められる。

#### 実装メモ

- `ProjectConfig.verify()` で `project_dir.resolve()` が `Path.cwd().resolve()` 配下かを `is_relative_to` で判定し、外れたら `ConfigValidationError`。`resolve()` を通すため絶対パス外部だけでなく相対 `../` 脱出も捕捉する（現状の `_another_mood_root` は anchor 判定のみで、相対 `../outside` は `.another-mood/../outside` に漏れている）。`.`（CWD 自身）は配下として許可。
- `project_dir` が CWD 配下保証となるため、`_another_mood_root` の basename フォールバック分岐は除去して簡素化する。
- 実装完了時、維持価値のある判断（キーの前提を `verify` で保証する点）は project-structure.md の External Design 節へ移し、この Proposals 節は削除する。

### 未実装の config キー

| キー | 型 | デフォルト | 環境変数 | CLI | タスク | 説明 |
|------|-----|---------|----------|-----|------|------|
| `render.customServer.command` | string | (なし) | `RB_RENDER_CUSTOM_SERVER_COMMAND` | — | G3 | カスタムレンダリングサーバのコマンド。設定時は Hugo の代わりに使用 |
