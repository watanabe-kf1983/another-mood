# Template Trust Model (appendix)

[Template Trust Model](../../../20-design/70-generator/25-template-trust-model.md) の背景。

## 信頼境界の二択

信頼境界の設計は本質的に次の二択:

| 望む世界 | 設計 |
|---|---|
| **「build = コードを走らせる」と理解させる**(ビルドツールとして正直に立つ) | **素の評価エンジン ＋ 危険注記**。untrusted build は OS / コンテナ隔離で守る。言語は不変 |
| **「テンプレは安全なコンテンツ、知らない人が無警戒に build してよい」を維持** | **non-evaluating エンジン**。知覚を「安全なコンテンツ」に保つには実態もそう作る |

採ったのは後者。中間形態を含めた比較検討は次節を参照。

## なぜ SandboxedEnvironment を採らないか（穴が N 個ではなく根が 1 個）

Jinja2 の SSTI 経路（`{{ ''.__class__.__mro__[1].__subclasses__() }}` の直接記法、`| attr('__class__')`、`| map(attribute='__class__...')` 等）は**独立した N 個の欠陥ではなく、単一の根から生えている**:

> Jinja2 の値モデルは「Python オブジェクトをリフレクションで触る」。全 Python オブジェクトは `__class__` を持ち、そこからオブジェクトグラフ全体（`os` / `subprocess`）へ到達できる。

したがって:

- **`SandboxedEnvironment`（Jinja2 の実行時サンドボックス）は実行時ブロックリスト** — 危険属性を都度「禁止」する。禁止漏れの属性パスが見つかるたびに脱出 CVE が出る、後手のイタチごっこ。しかも DoS 等は塞がず偽の安心を生む
- **穴を個別に塞ぐ発想も同じ轍** — `attr`/`map(attribute=)`/`selectattr`/`groupby` は string 属性名でリフレクションへ迂回でき、しかもこれらは showcase で属性ソート等に広く使われる load-bearing なフィルタ。フィルタごと禁止できず、許可リスト側で「属性文字列を安全なリテラルに制約」する必要がある

正しい対処は値モデルを叩くことではなく、**値モデルが構造的に安全なエンジンへ移す**か、**プロセス / OS 隔離**でビルドごと囲うか。上の二択に中間形態（実行時サンドボックス）が無いのはこのため — 言語を縛るが漏れる／隔離もしない、の両世界で中途半端になる。

採ったのは前者で、`Environment` は minijinja（`template_engine.py` の `make_environment`）。RCE は minijinja の値モデル ＋ marshal 契約で閉じ、DoS 対策（隔離 / リソース上限）はホスト / 無人 build のマイルストーンに送る。

## エンジン選定 — minijinja（spike 実測）

判定基準は **テンプレートに渡るデータが host 言語のリフレクション / capability への経路を運ぶか**。spike で 3 候補を実射した。

**python-liquid** — non-evaluating が言語仕様:

- 呼び出し構文が host allowlist（filter/tag）のみ ＝ **安全がバインディング非依存**。注入した capability オブジェクトすら *呼べない*
- 一方 macro 無し、`groupby`・`format`・文字列反復も無し ＝ 移行時にテンプレ logic をクエリ・custom filter へ押し出す必要がある（spike 時点の全テンプレ走査で要手当ては 3 箇所、いずれも「テンプレに漏れた logic」）

**minijinja（`minijinja-py`）** — 閉じた値モデル（Rust）:

- 評価器は Rust、素データは Rust `Value` に marshal され Python 不在 ＝ dunder 経路は**構造封鎖**
- **ただしそれだけでは RCE 閉包に不十分** — 渡したオブジェクトの非 `_` 属性・メソッドと global は露出し呼べる（[露出規則](../../../20-design/70-generator/25-template-trust-model.md#minijinja-の露出規則ssti-回帰テストで-pin)）。安全は**境界の marshal 契約**に懸かる
- Jinja 互換で書き直し最小（macro native・`env.finalizer` フックあり）。エラーは最厚（前後行＋キャレット＋参照変数）

**小さな自作評価器** — logic-less / 許可リスト:

- 言語は安全にできるが、真に難しい**コンテキスト別エスケープ**（`finalize`/`Markup`/whitespace）を再オープンする。不採

残る二択の軸は「**liquid ＝ 言語で構造保証**（未信頼テンプレを既定安全で build する世界）」対「**minijinja ＝ ほぼ drop-in ＋ marshal 契約**（自作・半信頼の世界）」。

**決定: minijinja 採用。** 決め手（spike 時点）:

- **移行コスト最小** — 当時 macro 使用 0・Jinja 互換（演算子 `~`/`//`/三項もそのまま通る）・`env.finalizer` フックあり
- **LLM 執筆性** — Jinja 系の訓練データを相続（Stack Overflow 質問数で Jinja 系 ≈ 40k、Liquid ≈ 4k の約 10 倍）
- **エラー品質** — minijinja / liquid とも jinja2 を上回る（キャレット＋前後行＋列、構造化フィールドで Diagnostic 化可）が、minijinja が最厚
- **移植性** — ブラウザ / WASM プレビューを作る場合、minijinja は Rust→WASM で**同一 engine**（最高忠実度）。liquid は python-liquid ＋ LiquidJS の別実装になる

安全は言語構造保証（liquid）ではなく marshal 契約で確保する。liquid は「未信頼テンプレを既定安全で build する」へ倒す場合の対抗案として残す。

## unsafe HTML の信頼前提との整合

Another Mood は **著者が所有するデータベース** をレンダーする SSG で、Hugo 既定の `unsafe=false`（untrusted な Markdown をレンダーするモデル向けの防御）とは前提が異なる。raw HTML を通しても露出は狭い: データ値 `{{ field }}` は md 出力 format の finalize で `md_escape` され（`<`→`\<`）無害化され、code span / fenced block の内容は Goldmark が `unsafe` と無関係に常に HTML エスケープする。新たに通る raw HTML は **著者自身のテンプレート・prose・(verbatim 外の) `| safe`** のみで、著者は既にソースとテンプレートの全権を持つため escalation にはならない。Hugo/Jekyll/MkDocs 等も自前コンテンツには unsafe HTML を許可するのが標準。

この raw HTML（bundled `resources/hugo/hugo.toml` の `unsafe = true`）の扱いは「著者は既にソースとテンプレートの全権を持つため escalation にならない」＝**著者 = 実行者**を前提に組まれている。これは著者が自分のsbdb プロジェクトに埋める HTML の話で、RCE 封鎖とは別レイヤ:

- unsafe HTML は「著者が自分の *出力* に責任を持つ」**表現力**の問題
- marshal 契約は「テンプレートが host の *コード* に届かない」**実行安全**の問題

**著者 ≠ 実行者**（第三者が配布されたsbdb プロジェクトを build）のケースは、RCE が閉じたぶん「build = コード実行」契約より安全 — これが non-evaluating エンジンを採る意義そのもの。残る差は「著者が unsafe HTML で書いた出力を第三者が信じるか」という *出力の信頼* で、実行安全とは独立に扱う。
