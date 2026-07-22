# プロジェクトマニフェスト (sbdb.yaml)

## Proposals

### プロジェクトマニフェストとフォーマット互換性 ([Q2](node:/tasks/Q/tasks/Q2))

#### 背景: 問題クラス

「人間が書いた成果物（フォーマット）を、独立に進化するツールが読む」系の互換性問題。
成果物とツールの新旧で 2×2 の行列ができ、対角以外の 2 マスが危険:

- **① 旧ソース + 新ツール**（後方互換）— ツールが旧世代の意味論を変えたのに旧ソースをそのまま解釈する
- **② 新ソース + 旧ツール**（前方互換）— 旧ツールが未知の構文を黙って読み飛ばす

どちらも「黙って壊れた出力が出る」silent 破損があり得る。Q2 の目的はこれを検出して
loud に失敗させること。マイグレーション（自動移行）はスコープ外。

#### 背景: 一般論の三道具

成熟したエコシステムはほぼ同じ道具立てに収斂している:

1. **edition 型**（Rust edition / Kubernetes apiVersion / Compose file version）—
   人間がソース内の一箇所に宣言。**破壊的変更のときだけ** +1。ツールは対応する版の
   集合を持ち、範囲外なら拒否。整数比較だけで①②両方向を守る。宣言欄の位置・形式は
   永久凍結（旧ツールも読めなければならないため）
2. **MSRV 型**（Rust rust-version / Terraform required_version / package.json engines）—
   「このソースはツール ≥ X が必要」の任意宣言。追加機能への依存を表明し、正確な
   「アップグレードしてください」エラーを出せる。宣言の陳腐化はエコシステム的に許容
3. **厳格パース**—未知の構文・キー・演算子を黙って読み飛ばさずエラーにする。
   宣言が無くても silent 破損だけは起こさない最終防衛線

②を分解すると: 新**構文**（仕様追加）は道具3 が構文エラーとして捕捉し、
既存構文の**意味変更**（破壊的変更）だけが本当に silent —— それは道具1 の管轄。
ゆえに edition は仕様追加では動かず、めまぐるしい改版サイクルは起きない。

なお、ビルド時の自動スタンプはマシンが書く成果物（lock ファイル・DB ファイル）の
道具であり、人間が書くソースへの版宣言はどのエコシステムでも人間の宣言で行う。

#### マニフェスト `sbdb.yaml`

`<projectDir>` 直下に置く（Cargo.toml / package.json の慣習。`contents/` の外なので
contents 編集者の視界に入らない）。

```yaml
edition: 1                  # 必須 — フォーマット世代（道具1）
title: My Project           # 任意 — 省略時はディレクトリ名にフォールバック（現行挙動）
tools:                      # 任意 — 各プロセッサの名前空間
  another-mood:
    requires: ">=0.3.5"     # 道具2 — このツールの最低バージョン
```

| フィールド | 必須 | 意味 |
|---|---|---|
| `edition` | **必須** | フォーマット世代。整数。欠落 = エラー（移行措置の節を参照） |
| `title` | 任意 | 表示名。トップページ等で使用。省略時はディレクトリ名 |
| `tools.<processor>.requires` | 任意 | プロセッサ固有の最低バージョン要求 |

`edition` を必須とする理由: 無ければチェック不能であり、「宣言忘れの新世代ソースを
旧世代として黙って解釈する」のは Q2 が防ぎたい silent そのもの。Cargo の
「省略 = 最古 edition」フォールバックは既存資産を壊せない事情ゆえの妥協で、
pre-1.0 の本ツールには不要。`mood init` / blueprint が自動で書き込むため新規利用者の
摩擦はない。author / license 等のメタ情報は additive に追加できるため今は載せない。

##### 背景: ツール中立性と `tools:` 名前空間

フォーマット（source-based DB, 識別子 **sbdb**）はツール中立のスペックであり、
Another Mood はその *a processor*（style guide の Means 定義）。ゆえにスペックの語彙に
ツール名を混入させない。道具2 は本質的に「ツールごと」の関心なので、pyproject.toml の
`[project]` / `[tool.<name>]` 分離に倣い `tools:` 名前空間に置く。将来別のプロセッサが
現れたら自分の行を持ち、他ツールの行は互いに無視する。

なお CWD 側の設定ファイル（[設定システム仕様](node:/prose/20-design/20-app/20-config-spec)
の G2）とは別物: config は「どうビルドするか」（環境・ツール設定、CWD 側）、
マニフェストは「このプロジェクトは何か」（識別・互換契約、projectDir 側）。

#### 読み込みと互換ゲート（二段読み）

1. **緩い抽出** — パイプラインの何よりも先に、凍結欄（`edition` /
   `tools.another-mood.requires`）だけを読む。未知キーがあってもこの段階では無視
2. **互換ゲート** —
   - `requires` があり実行中バージョンが不足 → 「mood を X 以上に上げてください」で
     即死（最も正確なエラー、パース前の fail-fast）
   - `edition` がツールの対応集合外 → 拒否。当面の対応集合は現行世代のみ
     （厳密一致）。対応レンジ `[Gmin..Gmax]` は将来、後方互換に拡張できる
3. **厳格検証** — ゲート通過後にマニフェスト全体を道具3 の対象として検証
   （未知キー拒否）

厳格検証をゲートの後に置く理由: 新 mood で書かれたマニフェストに未来のキーがあるとき、
旧 mood が「未知キー」で先に死ぬと `requires` のヒントを出す前に倒れるため。

**凍結面**: トップレベル `edition` の欄名・形式、および `tools.<name>` の形は永久凍結。
ここが動くと「バージョンを知るためにバージョン欄を読む」の鶏卵が壊れる。

#### 世代の運用

**外は単一カウンタ、中は面ごとの台帳。**

宣言・チェックの単位は単一の `edition` 番号のみ。面ごとの版ベクトルは持たない —
ほぼ全プロジェクトが全契約面を通るため面別の精度利得がなく、静止面
（schema-schema は JSON Schema サブセット制約に錨を下ろし、ほぼ動かない見込み）の
番号を全プロジェクトに書かせるのは死荷重になるため。

破壊的変更の判定は「この差分は以下の契約面のどれかを非互換に編集したか」に落ちる:

| 契約面 | 契約書 |
|---|---|
| schema | `resources/schemas/schema-schema.yaml` |
| query | `resources/schemas/query-schema.yaml` |
| parser/prose | Markdown 解釈規約 + `content-schema.yaml`（組み込み prose/blob）+ 埋め込み構文 |
| template | フィルタ・タグ・グローバルの登録面（コードが契約） |
| layout | プロジェクト配置規約（`definition/` / `contents/`） |
| manifest | `sbdb.yaml` 自体（凍結欄を除く） |

contents はこの台帳に**独立の行を持たない**: YAML レコードを縛る契約はユーザの
schema.yaml であり、mood の変更が contents の意味を変える事態は必ず schema 面か
parser/prose 面の変更として現れる。ゆえに版宣言は definition 側の関心で、
contents 編集者は versioning の存在を知らなくてよい。

**世代台帳**（世代を上げたらどの面がどう動いたかをここに追記する。エラーメッセージ・
移行ガイドの粒度はこの台帳から得る）:

- **edition 1** — 初期契約

**Q6 との関係**: mood の 0.MINOR bump ⇔ edition +1 の 1:1 対応
（[Q6](node:/tasks/Q/tasks/Q6)）は mood 側のリリース規律であり、スペックの性質ではない。
スペックが所有するのは edition のみ。リリースチェックリストの「フォーマット世代 +1
判定」は上の契約面台帳を具体的なチェック項目として使う。

#### 道具3 の現状と設計義務

監査結果（2026-07）: **完備**。

- schema / query / contents(YAML): メタスキーマが `additionalProperties: false` を徹底
  しており未知キーは検証エラー
- template: 未知タグ = `TemplateSyntaxError`、未知フィルタ = `TemplateAssertionError`、
  グローバルは callable のみで Undefined の呼び出しは `UndefinedError` — mood 由来の
  名前はすべて loud。変数・フィールド参照の `ChainableUndefined`（空文字）は
  ユーザデータ由来の名前に対する書き味の設計であり、バージョン互換の穴ではない
  （mood の機能追加でテンプレート変数が増えることはない — そこはユーザ定義領域）

**設計義務として明文化**: mood 由来の語彙（スキーマキー・クエリ演算子・タグ・
フィルタ・マニフェストキー）に対する未知の入力は、黙って読み飛ばさずエラーにする。
将来の機能追加はこの性質を保つこと。これが版宣言を持たない/更新しない利用者への
最終防衛線になる。

#### 命名

- フォーマット識別子は **sbdb**（source-based DB）。style guide の表記規約に追記する
- **`mood_view` → `render` 改名**: スペック語彙への唯一のツール名混入を、公開前の
  今のうちに解消する。Q2 本体の前哨タスク（[P4](node:/tasks/P/tasks/P4)、
  エイリアス廃止は [P5](node:/tasks/P/tasks/P5)）として別ブランチで実施。
  改名後のタグ名は `render` に確定。当初の推奨候補 `view` は、query が生成する
  名前付きデータセットの正式名称「ビュー」（`docs/reference/query.md`）と
  同一 namespace 感覚で語彙衝突し、しかもタグの引数は view 名ではなくテンプレート
  ファイル名なので誤読を誘う。`page` は inline 展開時に嘘になる（ページか否かを
  決めるのはタグではなく `file_per`）。`render` は split/inline 両モードで意味論が
  正確、docs リファレンスの既存記述（"render a subtemplate…"）と一致し、
  Shopify Liquid の `{% render %}`（スコープ分離 + 明示的データ受け渡し）に先例がある。
  Jinja 組み込みタグ・既存フィルタとも非衝突

#### 移行措置

既存の稼働プロジェクトが 1 件あり（利用者は把握済み）、以下の猶予を置く。
警告は出さない — 唯一の利用者が事情を把握しており、周知の必要がないため:

- `mood_view` は**警告なしの静かなエイリアス**として `render` と併存
  （[P4](node:/tasks/P/tasks/P4)）。廃止（[P5](node:/tasks/P/tasks/P5)）は稼働
  プロジェクトの移行完了後、[Q1](node:/tasks/Q/tasks/Q1)（PyPI 公開）前
- `sbdb.yaml` 欠落時は**警告なしで edition 1 とみなして続行**。必須化の期限は
  min(Q1, 最初の edition bump) — edition が複数になった瞬間に「欠落 = 1」の仮定は
  ambiguous になるため、これは運用判断ではなく構造的期限。公開後は未知の利用者が
  現れるため、いずれの猶予も Q1 までに必ず畳む

#### 実装スコープ

前哨（別ブランチ）:

- `mood_view` → `render` 改名（静かなエイリアス併存、[P4](node:/tasks/P/tasks/P4)。
  エイリアス廃止は [P5](node:/tasks/P/tasks/P5)）

本体（カテゴリ V）:

1. [V1](node:/tasks/V/tasks/V1) — `sbdb.yaml` の読み込みと edition ゲート（二段読み）
   + `title` のトップページ表示（現行のディレクトリ名直渡しをフォールバックに降格）
2. [V2](node:/tasks/V/tasks/V2) — `tools.<processor>.requires` の fail-fast
3. [V3](node:/tasks/V/tasks/V3) — 生態系への展開: `mood init` / blueprint の生成、
   showcase / dev-docs への付与、`docs/` reference のマニフェスト章 + style guide への
   sbdb 表記追記（稼働プロジェクトへの付与はリポジトリ外の作業のため P5 と同じ籠）
