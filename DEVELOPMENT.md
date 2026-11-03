# Development Guide

## Conventions (Must Read)

### 開発ワークフロー

- タスク開始時に `make ci` を実行し、開発環境・既存コードが正常な状態であることを確認する
- タスク開始時に `make upgrade-deps` で uv.lock の鮮度も確認する。diff が出るとスクリプトが lock 単独 PR の作成（push を含む）まで行うので、その PR を merge してから着手する（規約の全体は [dev/dependencies.md](.another-mood/dev-docs/output/web/prose/30-dev/35-dependencies.md)）
- コミットメッセージ・プルリクエストは **英語**

### セットアップ

環境構築は [dev/environment.md](.another-mood/dev-docs/output/web/prose/30-dev/10-environment.md)。

このプロジェクト自身が Another Mood でドキュメントを管理している。タスク開始時には `mood build dev-docs` でドキュメントをビルドし、仕様が参照できる状態にする。起点は [.another-mood/dev-docs/output/web/index.md](.another-mood/dev-docs/output/web/index.md)。

利用者向けサンプルプロジェクト群は `showcase/`（`starter` / `music` 等の各テンプレート）にある。`mood build showcase/{name}` でビルドできる。

### ドキュメント

何かを知りたいとき、開く場所は情報の種類ごとに一つ。コードから読めるもの（機構、現在の挙動）はコードを読む。文書が持つのは、コードから復元できないもの（約束、意図、不変条件、判断の過程）だけ。

開く場所は「何についてか」と「どの深さか」の二軸で決まる。各行は左から読み、必要なときだけ右へ進む:

| | 導線・約束（まず読む） | 精密な条件（必要なときに開く） | 実際の姿（実装の写し） |
|---|---|---|---|
| 利用者から見える挙動 | `docs/reference/` | `dev-docs/design/` の外部設計（意図して保つ振る舞いと、その理由） | fixture テスト |
| 内部の構造 | `dev-docs/design/` の内部構造（層とステージの構成と、それを保つ約束） | docstring（呼び出し側の契約）、コメント（申し送り） | コード |
| 開発の進め方 | 本ファイル | `dev-docs/dev/` | Makefile・CI 等の設定 |

契約は左上の `docs/reference/` だけで、破壊的変更の判定はその diff で行う。他の欄は安定させる意図があっても約束ではなく、変更はリリースノートの義務を生まない。

格子にあるのは「いま何がそうなっているか」。「なぜそうなったか」と「次に何をするか」は欄に収まらないので、別の場所で読む:

- **なぜそうなったか** — 意図は対象と同じ場所にある（該当する欄の中の一文）。そこに至った過程（比較、却下案、経緯）は PR 本文、つまり main の git log
- **次に何をするか** — 目的は `dev-docs/concept/`、やることは GitHub Issues

言語は `docs/` が英語、`dev-docs/` が日本語。書く側の規約（各置き場の読者、何を書き何を書かないか、インデックスの更新）は [dev/documentation.md](.another-mood/dev-docs/output/web/prose/30-dev/45-documentation.md)。

### 実装

- コード内コメントは **英語**
- 散文では `Another Mood`、パス・パッケージ名等の識別子では `another-mood` / `another_mood`、コマンドは `mood`（表記規約は [dev/style-guide.md](.another-mood/dev-docs/output/web/prose/30-dev/40-style-guide.md)）
- ライブラリ導入は、その時点での有力なものを比較検討したうえで決定する。**選定理由はそのライブラリを使う箇所のコメントか docstring に一文で残し、比較の過程は PR 本文に書く**。版の制約は下限のみ（規約は [dev/dependencies.md](.another-mood/dev-docs/output/web/prose/30-dev/35-dependencies.md)）
- docstring は API の呼び出し側に補足が必要な契約のみ（可能ならシグネチャで表現する）。コメントは将来の保守者への申し送りのみ。申し送る理由が契約や外部設計にあるなら、その節や見出しを名指す

#### パッケージ構成と依存ルール

主な登場人物。網羅ではない:

```
another_mood/
├── cli.py                  # CLI エントリポイント
├── command.py              # CLI の背後の操作層（BuildResult 等を返す）
├── config.py               # 設定
├── components/             # ビジネスロジック
│   ├── shared/             #   共通基盤
│   ├── preprocess/         #   入力の正規化・スキーマ解釈・クエリ導出
│   ├── composer/           #   合成: データ + クエリ → ビュー
│   ├── generator/          #   生成: ビュー + テンプレート → Markdown
│   └── publish/            #   出力の書き出し
├── pipeline/               # オーケストレーション: ステージ実行
│   └── adapters/           #   外部ツール連携（Hugo, watchdog）
└── resources/              # 静的リソース
```

依存方向: `cli` → `command` → `pipeline` → `components/*` → `components/shared`。コンポーネントは互いも pipeline も import しない。各層の役割とステージの構成は [design/Architecture](.another-mood/dev-docs/output/web/prose/20-design/20-internal/10-architecture.md)。

#### コードスタイル

- **関数型スタイルを優先**: `for` ループより内包表記、`map/filter` 等。引数・戻り値はイミュータブル型（`dict` → `Mapping`、`list` → `Sequence` 等）
- **`Any` はなるべく使わない**: `object` 等で型安全性を保つ
- **命名はモジュール名に合わせる**: `source` モジュールなら `is_source_file`, `build_source`
- **関数の並び順（Newspaper style）**: 公開 API を先頭、ヘルパーを後ろ。ヘルパーはパイプライン順
- **`@dataclass` は `frozen=True`**: `__init__` ボイラープレート削減目的、immutable がデフォルト
- **制御フローは論理の形に合わせる**: 両枝が対等な結果を返す *対称な分岐* は `if/else`（両枝が `return` でも `else` を畳まない）。前提失敗・エラー・エッジを先頭で剥がす *非対称な bail-out* のみ guard clause（早期 `return`）
    - `else` とインデントは条件付き領域の境界情報なので、機能的に冗長でも残す（*explicit is better than implicit*）

#### テスト

- **単体テストで覆うのは `components/`**: ビジネスロジックはここに置き、`cli` / `command` / `pipeline` は薄く保つ。カバレッジ（statements + branches）は `make ci` が 90% で守る
- **フィクスチャ**: ファイルベース、モジュール隣接型。期待値はテストコード内に記述
- **約束を守るテストは、守る約束を名乗る**: docstring の一行目に、契約の節（`Keeps: docs/reference/view.md › Missing-key placement`）か外部設計の見出し（`Keeps: design/View › flatten 後の行は、親の属性を残し、要素を as: の下に置く`）を書く
    - 名乗るのは、その約束を破ったとき最初に落ちるテストだけでよく、網羅は求めない。契約や外部設計の節を変えるときは、節名で grep して名乗るテストを直す

#### 動作確認

テンプレートの変更を実機で確かめるときは `mood watch <project_dir> --port <port>` でプレビューを上げ、必要なら Playwright MCP で観る（作業ファイルの置き場は [dev/environment.md](.another-mood/dev-docs/output/web/prose/30-dev/10-environment.md) の「Playwright の作業ファイル」節）。

### プルリクエスト

PR 本文はそのまま main の squash コミット本文になる（ブランチ上のコミットメッセージは残らない）。変更の要約と、設計判断の背景・経緯はここに書く。タイトルは利用者が読むリリースノートに載るので、内部語彙を置かない。

リリースノート冒頭のハイライトに載せたい PR は、PR 本文の末尾に行頭からトレーラーを一行書く。kind は `breaking` / `feature` / `fix`:

    Release-Highlight: <kind>

`breaking` だけは義務で、`## Breaking change` セクションを伴う。kind の選び方、破壊的変更（サポート世代の脱落・CLI 等の利用者向け契約の破壊）を含む PR の義務、リリース手順は [dev/release.md](.another-mood/dev-docs/output/web/prose/30-dev/50-release.md)。

## Documentation (Reference)

ドキュメントの閲覧先は `.another-mood/dev-docs/output/web/`。

- [index.md](.another-mood/dev-docs/output/web/index.md) — 仕様・設計
- [concept/product.md](.another-mood/dev-docs/output/web/prose/10-concept/10-product.md) — 製品ビジョン
- [dev/style-guide.md](.another-mood/dev-docs/output/web/prose/30-dev/40-style-guide.md) — 命名・自己定義の表記規約
- [dev/documentation.md](.another-mood/dev-docs/output/web/prose/30-dev/45-documentation.md) — ドキュメントの書き方（置き場ごとの読者と規約）
