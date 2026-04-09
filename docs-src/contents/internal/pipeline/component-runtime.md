# Component Runtime（リファクタ設計）

各コンポーネントの「実行・出力先・排他制御・エラー伝播」を担う共通基盤の再設計。

このドキュメントは未実装の TOBE。実装着手時は本ドキュメントを唯一の引き継ぎとして利用し、完了後はコードから読み取れる内容を削除して「## 背景」セクションに集約する（[DEVELOPMENT.md](../../../../../DEVELOPMENT.md) の internal/ 整理ポリシー参照）。

## 動機

現状の構造には次の問題がある:

1. **データ層に制御メタデータが漏れている**: 各コンポーネントの `out_dir` 直下に `__build_report.yaml` が同居しているため、下流の本処理（`shutil.copytree`、`load_yamls` 等）が build_report を意識する必要がある。Composer では `shutil.ignore_patterns("__build_report.yaml")` で個別に除外しており、cross-cutting な汚れになっている。
2. **Component / Pipeline / Config が密結合**: 各コンポーネントの中間出力先パス（`data_catalog_dir`, `normalized_contents_dir`, `views_dir` 等）を `ProjectConfig` が個別フィールドとして持っており、stages.py が path を bind する。新しいコンポーネントを足すたびに 3 ファイル（config・stages・コンポーネント）を変える必要がある。
3. **`atomic_write` の命名が誤解を招く**: 実装は FileLock + version.json による「複数プロセス間の排他制御 + バージョン順序保証」であり、「下流から見て中間状態が見えない」という本来の atomic 性は提供していない（in-place sync）。「下流からの見え方」を atomic だと誤解すると、本来できない保証に依存した設計を生んでしまう（実際に Composer 周辺で混乱があった）。

## 設計原則

1. **コンポーネントは自己完結したカプセル**: 1 コンポーネント = 1 ディレクトリ（`tmp/<component_name>/`）。データも build_report もその下に閉じ込め、コンポーネント外からの参照経路を `tmp/<component_name>/data/` と `tmp/<component_name>/reports/` の 2 つに限定する。
2. **データチャネルとレポートチャネルの分離**: 本処理が読み書きするのは `data/` のみ。エラー伝播のメタデータは `reports/` のみ。本処理はレポートを一切意識しない。
3. **同じ排他境界で書く**: `data/` と `reports/` は同じ `exclusive_write` 境界で書く。同じコンポーネントの 2 つの実行インスタンスが混ざらない（data は実行 A のもの、reports は実行 B のもの、という整合性破綻を防ぐ）。
4. **コンポーネント名から path を導出**: Component decorator が `name` と `upstream_components` を持ち、`tmp_dir` ベースから自動でパスを解決する。Config と stages.py からコンポーネント中間出力先のフィールドを撤去する。
5. **publish は通常 Stage**: ユーザに見せたい成果物（generator の出力）を `out_dir` に転写するステップは Component ではなく Pipeline 上の通常 Stage として実装する。Pipeline 上に並ぶものが必ずしも Component である必要はない（既存の `build_report_stage` と同じ位置付け）。

## 新レイアウト

```
.reqs-builder/<project>/
├── tmp/
│   ├── inspect_schema/
│   │   ├── data/                  ← schema_inspector の出力
│   │   └── reports/build_report.yaml
│   ├── normalize_contents/
│   │   ├── data/
│   │   └── reports/build_report.yaml
│   ├── normalize_queries/
│   │   ├── data/
│   │   └── reports/build_report.yaml
│   ├── compose/
│   │   ├── data/                  ← contents/, data-catalog/, queries/, query-results/
│   │   └── reports/build_report.yaml
│   └── generate/
│       ├── data/
│       └── reports/build_report.yaml
├── output/                        ← publish stage が tmp/generate/data から copytree
└── render/                        ← Hugo 出力（既存）
```

`tmp/<name>/` 全体が 1 つの `exclusive_write` 境界（FileLock + version.json）で守られる。`data/` と `reports/` は同じ境界内なので、同じ実行インスタンスのものが対で flip される。

## Component decorator

```python
@Component(
    upstream_components=["inspect_schema"],
)
def normalize_contents(
    src_dir: Path,
    *,
    schema_dir: Path,
    out_dir: Path,
    data_catalog_dir: Path,  # 上流コンポーネント名から自動で bind
) -> None:
    ...
```

### 責務

Component decorator が持つ情報:
- `name`: `fn.__name__`（コンポーネント自身の名前）
- `upstream_component_names`: 上流コンポーネント名のリスト

bind 時に `tmp_dir` を受け取り、以下を解決して関数に渡す:
- `out_dir = tmp_dir / name / "data"`（自身の出力）
- `<upstream_name>_dir = tmp_dir / <upstream_name> / "data"`（上流の出力。kwarg 名は引数名から決まる規約 or 明示マッピング — 実装時に決める）
- `report_dir = tmp_dir / name / "reports"`（error_propagation が使用、関数本体には渡さない）
- `upstream_report_dirs = [tmp_dir / <upstream_name> / "reports" for ...]`（同上）

### 関数本体のシグネチャは不変

関数本体は今までどおり `out_dir: Path` と上流入力 dir を kwarg で受け取る。Component decorator が bind を肩代わりするだけ。**単体テストは関数を直接呼ぶ既存スタイル（`compose(contents_dir=..., out_dir=tmp_path / "out")`）がそのまま使える**。

### 排他制御とエラー伝播の順序

現状の `_run` の入れ子構造（`exclusive_write` の内側で `error_propagation`、その内側で本処理）を維持する:

```
exclusive_write(tmp/<name>):           ← FileLock + version 順序保証
    error_propagation(...):             ← 例外を捕まえて report に書く
        try:
            self.fn(...)
        except Exception as exc:
            report.add_data(_error_data(exc))
        report.write(report_dir)
```

例外が発生しても `error_propagation` が捕まえて report に書き出すため、`exclusive_write` から見れば常に正常終了。data と reports が同じ境界内で flip される。

## stages.py の API

`component_stage` ヘルパで重複を消す。素案:

```python
def normalize_contents_stage(config: ProjectConfig) -> Task:
    return component_stage(
        normalize_contents,
        config,
        extra_kwargs={
            "src_dir": config.contents_dir,
            "schema_dir": config.schema_dir,
        },
        extra_watch_paths=[config.contents_dir, config.schema_dir],
    )

def compose_stage(config: ProjectConfig) -> Task:
    return component_stage(compose, config)

def inspect_schema_stage(config: ProjectConfig) -> Task:
    return component_stage(
        inspect_schema,
        config,
        extra_kwargs={"schema_dir": config.schema_dir},
        extra_watch_paths=[config.schema_dir],
    )
```

`component_stage` の責務:

1. Component の `upstream_component_names` を元に `tmp_dir / <upstream> / data` を上流入力として bind
2. `extra_kwargs`（ユーザ入力 dir 等）を bind
3. `out_dir` と report 系を Component decorator が解決
4. watch_paths = `[tmp_dir / <upstream> / reports for ...] + extra_watch_paths`

watch 対象は **上流の reports のみ**（上流の data ではない）。理由: error_propagation は成功時も失敗時も必ず report を書くため、report の更新は「ステージが完走した」イベントそのもの。data の変化を watch する必要はない。

### publish stage

`publish` は Component ではなく通常 Stage として実装:

```python
def publish_stage(config: ProjectConfig) -> Task:
    src = config.tmp_dir / "generate" / "data"
    dst = config.out_dir
    return Stage(
        run_fn=lambda: shutil.copytree(src, dst, dirs_exist_ok=True),
        watch_paths=[config.tmp_dir / "generate" / "reports"],
    )
```

publish 自身は build_report を持たない。失敗したら例外を投げて Pipeline が止まる、で十分。

### build_report_stage

watch_paths を `[tmp_dir / "generate" / "reports"]` に変更（最下流コンポーネントの reports のみ）。

## ProjectConfig のスリム化

```python
class ProjectConfig:
    project_dir: Path

    # User-edited inputs
    contents_dir: Path
    schema_dir: Path
    queries_dir: Path
    templates_dir: Path

    # Outputs
    tmp_dir: Path                  # rb / "tmp"
    out_dir: Path                  # rb / "output"
    render_in_dir: Path
    render_out_dir: Path

    port: int
```

削除されるフィールド:
- `data_catalog_dir`
- `normalized_contents_dir`
- `normalized_queries_dir`
- `views_dir`
- `definition_dir`（今も実質未使用）

これらはすべて `tmp_dir / <component_name> / data` で導出される。

## `atomic_write` の改名

`atomic_write` → `exclusive_write`。

理由: 現実装は FileLock による排他制御 + version.json による順序保証であり、「下流から見た中間状態の不可視性」という意味の atomic 性は提供していない（in-place sync のため、下流の watcher は中間状態を観測しうる）。本質である「複数プロセス間の干渉防止 = 排他」を名前で表現する。

このリファクタの中で API 名（モジュール名・関数名・context manager 名）をすべて変更する。

## 実装計画

互いに密結合した変更だが、レビュー単位として 3 ステップに分けて独立 PR で進める:

### Step 1: `atomic_write` → `exclusive_write` 改名

意味論は変えず、純粋なリネームのみ。

- `atomic_write.py` → `exclusive_write.py`
- 関数 `atomic_write` → `exclusive_write`
- 利用箇所（`component.py`, テスト, ドキュメント）の追従

レビューコストを最小化する。次の Step の前提を整える。

### Step 2: コンポーネント出力先の自動導出と publish stage 追加

`Component` decorator にコンポーネント名ベースの自動 bind を導入する。出力レイアウトは「`tmp/<name>/`」（中間に `data/` を挟まない）に変更し、publish stage を追加。

- `Component` decorator に `upstream_components` を追加、`name` から `out_dir` を自動 bind
- `ProjectConfig` から中間出力先フィールドを撤去
- `stages.py` に `component_stage` ヘルパを導入し、各 stage 関数を簡略化
- `publish_stage` を追加し、`tmp/generate/` を `out_dir` にコピー
- `BuildReport.collect` の参照先を変更
- 各コンポーネントのテストはシグネチャ不変なので原則そのまま

この時点では `__build_report.yaml` は依然として `tmp/<name>/` 直下に置かれ、`load_yamls` から見える（Composer の `ignore_patterns` も残る）。

### Step 3: data / reports の分離

`tmp/<name>/data/` と `tmp/<name>/reports/` の subdir 構造を導入し、本処理がレポートを意識しなくて済むようにする。

- `Component` decorator が `out_dir = tmp/<name>/data`、`report_dir = tmp/<name>/reports` を別々に bind
- `error_propagation` が `report_dir` に書き込むよう変更（`out_dir` から完全に独立）
- `BuildReport.collect` が `reports` のみを読むよう変更
- Composer から `_IGNORE_BUILD_REPORT` を削除
- Generator のエラーページ生成ロジックを `report_dir` ベースに変更
- `exclusive_write` が `tmp/<name>/` 全体を 1 境界として扱う（data と reports を同じ排他境界に入れる）

## 背景

### なぜコンポーネント単位カプセル化（案 P）か

設計検討時に 2 案を比較した:

- **案 P (per-component)**: `tmp/<name>/{data,reports}/`
- **案 G (grouped)**: `tmp/{data,reports}/<name>/`

差は微妙だが、案 P を採用した決定打は **`exclusive_write` の排他境界がコンポーネント単位で 1 つにまとまること**。案 G だと `tmp/data/<name>` と `tmp/reports/<name>` が別の lock / 別の version.json を持つことになり、同じコンポーネントの 2 つの実行インスタンスが混ざる可能性が論理上ありえる（実行 A の data + 実行 B の reports という組み合わせ）。これは debounce では補えない、整合性レベルの保証。

副次的な利点:
- コンポーネント単位でディレクトリ移動・削除・観察ができる
- 「`tmp/<name>/` を見ればそのコンポーネントの全状態がわかる」というメンタルモデルが綺麗

案 G の利点（`BuildReport.collect(tmp/reports)` で一括収集できる、`tmp/reports/` をデバッグ時に一覧で見やすい）は、Pipeline がコンポーネント名を列挙することで吸収可能。Pipeline がパイプラインの形を知っているのはむしろ自然。

### なぜ data と reports を同じ排他境界に入れるか

`exclusive_write` の本質は「複数プロセスの干渉防止」であり、「下流から見た atomicity」ではない（in-place sync）。下流から見た中間状態の問題は debounce で十分潰せる。

しかし、**同じコンポーネントの 2 つの実行インスタンスが混ざる**問題は debounce では解決できない。これは時間軸の問題ではなく、ファイル所有権の問題。

| シナリオ | 案 P | 案 G |
|---|---|---|
| プロセス A と B が同時に compose を実行 | 1 つの lock で排他 → A → B の順に直列化、各実行の data + reports が対で flip | data lock と reports lock が独立。A の data と B の reports が混ざる可能性 |
| 下流 watcher が中間状態を観測 | flip 中間状態は debounce window 内 → 1 回の発火にマージ | 同上 |

つまり「中間状態が下流から見える / 見えない」は debounce の問題で両案同じ。「コンポーネントの 2 実行が混ざらない」は排他境界の問題で案 P 優位。

### なぜ `atomic_write` は誤名か

`atomic_write` という名前は、CS 一般用語としては「**書き込みが他から見て分割不可能 = 中間状態が観測できない**」を期待させる。データベースの ACID の A や、POSIX の `rename(2)` の atomicity と同じ意味。

しかし現実装は:
- `tempfile.mkdtemp` で一時ディレクトリを作る
- 本処理が一時ディレクトリに書く
- ロックを取って `out_dir` の中身をクリアし、一時ディレクトリの中身を **in-place で copy** する
- ロックを放す

つまり最終ステップは `out_dir/foo`, `out_dir/bar`, ... を 1 ファイルずつ書いていくため、watcher 視点では中間状態が観測できる。本来の atomic ではない。

実装の本質は:
- **FileLock**: 複数プロセスが同じ `out_dir` を同時に触らない
- **version.json**: 古いビルドが新しいビルドを上書きしない（時刻順序の保証）

これは「排他制御 + バージョン管理」であり、`exclusive_write` の方が正確。

このプロジェクト内で `atomic_write` という名前にミスリードされて、設計議論中に「下流から見た atomicity がある」と誤った前提を立てかけたことがあった（Phase 7 改修中の議論で発覚）。**名前と実装の乖離が設計判断を歪める実例**として、本リファクタで一掃する。

### なぜ publish は Component ではなく通常 Stage か

検討時の選択肢:
- (a) publish も Component。`tmp/publish/data/` を経由してから out_dir にコピー（二度コピー）
- (b) publish は Pipeline 上の通常 Stage。Component の規約から外れる

(b) を採用。理由:
- (a) は二度コピーで気持ち悪い
- (a) は「Component の `out_dir` は `tmp/<name>/data`」という規約と「publish の最終出力先は `out_dir`」という現実が矛盾する。これを解決するために規約に例外を入れると規約の価値が落ちる
- そもそも Pipeline 上に並ぶものが必ずしも Component である必要はない。既存の `build_report_stage` も Component ではない通常 Stage であり、publish もこれと同じ位置付けが自然

publish 自身は build_report を持たない（失敗したら例外を投げて Pipeline が止まる、で十分）。
