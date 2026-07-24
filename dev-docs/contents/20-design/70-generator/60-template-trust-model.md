# Template Trust Model

テンプレートエンジンの信頼境界 — 「誰が書いたテンプレートを、誰の手元で実行するか」— の設計。`build` / `watch` はプロジェクトのテンプレートを評価するため、この境界 — テンプレートが host のコードに届きうるか — が製品の安全性を規定する。

利用者向けの注意書き（`build` / `watch` の信頼契約）は `docs/` を参照。本仕様は設計判断に絞る。

## External Design

### 信頼モデル (0.1.0): テンプレートは閉じた値モデルで評価する（RCE 構造封鎖）

0.1.0 は **minijinja（閉じた Rust 値モデル）＋ marshal 契約**で出荷する（P6 / P9）。テンプレートは host 言語のリフレクション / capability への経路を持たない値の上で評価されるため、**build / watch で第三者のプロジェクトを走らせても任意コード（RCE）は走らない**。dunder 経路は minijinja が構造封鎖し、非 `_` 属性・メソッド・globals は marshal 契約が封じる（機構は [Proposals](#proposals)）。

ゆえに `make` / `npm install` / Jekyll 型の「build = コードを走らせる」契約とは異なり、テンプレートを安全なコンテンツとして扱える。**`docs/` に RCE の危険注記は置かない** — RCE が閉じている以上、注記は過剰警告になる。

残る攻撃面は **DoS**（`"x" * 10**12` 等のメモリ爆弾・`{% for %}` 無限ループ）のみで、ローカル CLI では Ctrl-C の accepted-risk。リソース上限は無人 / ホスト build を導入するマイルストーンで入れる（[Proposals](#proposals) の DoS 節）。

### 背景: なぜ A（注記のみ）でなく C を 0.1.0 から採るか

当初案は 0.1.0 を **A**（素の Jinja2・「テンプレートは信頼された入力」・「build = コード実行」の危険注記のみ）とし、C を 1.0 の配布機能に送るものだった。C を 0.1.0 へ前倒ししたのは:

- **engine 差し替え（P6）が実測で drop-in** — minijinja は Jinja 互換で macro 0、exotic filter（`groupby` / `format` / `selectattr` 等）も演算子（`~` / `//` / 文字列反復）も `+` 空白制御も素通り、undefined 連鎖は `undefined_behavior="chainable"` で吸収。parity のテール risk が無い
- **marshal 契約（P9）が軽量** — 型＋composer 構築点の 1 assert ＋ CI テスト。Node の `_` 予約接頭辞が minijinja の `_` ブロックと一致し大半を肩代わりする
- **render=filter（P7 / P8）で 0.1.0 前にどのみちテンプレを触る** — 1 回の改修で engine まで倒せ、**後の破壊的移行と危険注記を両方回避**できる

配布（1.0）の hard predecessor だった安全化が 0.1.0 で済むため、配布機能はこの順序事故から解放される。

### 背景: 実行ベクタはテンプレートのみ

ソース4種のうち host コードへの経路を持ちうるのはテンプレートだけ（C の値モデルでそれも封鎖）で、他3種はそもそも経路を持たない:

- **`contents/` (data)** — data 値は md output format の finalize で escape される（[anchor-spec.md](20-anchor-spec.md) の unsafe トラストモデル参照）
- **`definition/schema.yaml`** — 宣言的な型定義
- **`definition/queries/`** — 境界付きの宣言 DSL（`from`/`flatten`/`join`/`where`/`grouped`/`select`/`sort`）。`where` 述語は演算子の閉じた enum（`EQ`/`GT`/`STARTSWITH`/`CONTAINS` 等）を `and`/`or`/`not` で結合するだけで、フィールド参照は dotted-key lookup（Python の `getattr` ではない）。`eval`/`exec`/式言語は無い（[record_predicate.py](../../../../src/another_mood/components/shared/record_predicate.py)）

ゆえに防御は**テンプレート評価の一点**（engine の閉じた値モデル ＋ marshal 契約）に集約してよい。

### 背景: unsafe HTML の信頼前提との整合

[anchor-spec.md](20-anchor-spec.md) の raw HTML（`unsafe=true`）は「著者は既にソースとテンプレートの全権を持つため escalation にならない」＝**著者 = 実行者**を前提に組まれている。これは著者が自分のプロジェクトに埋める HTML の話で、C（RCE 封鎖）とは別レイヤ — unsafe HTML は「著者が自分の *出力* に責任を持つ」表現力の問題、marshal 契約は「テンプレートが host の *コード* に届かない」実行安全の問題。

**著者 ≠ 実行者**（第三者が配布プロジェクトを build）のケースは、C の下では RCE が閉じたぶん A より安全になった — これが 0.1.0 から C を採る意義そのもの。残る差は「著者が unsafe HTML で書いた出力を第三者が信じるか」という *出力の信頼* で、実行安全とは独立に扱う。

## Internal Design

### 背景: なぜ SandboxedEnvironment を採らないか（穴が N 個ではなく根が 1 個）

Jinja2 の SSTI 経路（`{{ ''.__class__.__mro__[1].__subclasses__() }}` の直接記法、`| attr('__class__')`、`| map(attribute='__class__...')` 等）は**独立した N 個の欠陥ではなく、単一の根から生えている**:

> Jinja2 の値モデルは「Python オブジェクトをリフレクションで触る」。全 Python オブジェクトは `__class__` を持ち、そこからオブジェクトグラフ全体（`os` / `subprocess`）へ到達できる。

したがって:

- **`SandboxedEnvironment`（B）は実行時ブロックリスト** — 危険属性を都度「禁止」する。禁止漏れの属性パスが見つかるたびに脱出 CVE が出る、後手のイタチごっこ。しかも DoS 等は塞がず偽の安心を生む
- **穴を個別に塞ぐ発想も同じ轍** — `attr`/`map(attribute=)`/`selectattr`/`groupby` は string 属性名でリフレクションへ迂回でき、しかもこれらは showcase で属性ソート等に広く使われる load-bearing なフィルタ。フィルタごと禁止できず、許可リスト側で「属性文字列を安全なリテラルに制約」する必要がある

正しい対処は値モデルを叩くのではなく、**値モデルが構造的に安全なエンジンへ移す**（C ＝ minijinja）か、**プロセス / OS 隔離**でビルドごと囲う。0.1.0 は前者を採り、`Environment` を minijinja へ差し替える（[template_engine.py](../../../../src/another_mood/components/generator/template_engine.py) の `make_environment`）。RCE は minijinja の値モデル ＋ marshal 契約で閉じ、DoS 対策（隔離 / リソース上限）はホスト / 無人 build のマイルストーンに送る。

## Proposals

未実装。1.0 の配布 / 共有機能に向けて詰める。

### 段階論: C を 0.1.0 から採る

信頼境界の選択肢は本質的に二択で、B は両世界で中途半端（言語を縛るが漏れる／隔離もしない）ゆえ不採:

| 望む世界 | 設計 |
|---|---|
| **「build = コードを走らせる」と理解させる**（ビルドツールとして正直に立つ） | **A ＋ untrusted build は OS / コンテナ隔離**。言語は不変、showcase もそのまま |
| **「テンプレは安全なコンテンツ、知らない人が無警戒に build してよい」を維持** | **C（non-evaluating エンジン）**。知覚を「安全なコンテンツ」に保つには実態もそう作る |

**決定: 0.1.0 から C（minijinja ＋ marshal 契約）。** 当初は A@0.1.0（注記のみ）→ C@1.0 の段階論だったが、C の実測軽量さ（[背景節](#external-design)）ゆえ前倒しした。C は **P6（engine 差し替え）＋ P9（marshal 契約）**で構成し、両者 phase 14（Q1 = 0.1.0 公開の前）。依存の鎖は **P7（render filter 追加）→ P8（タグ廃止）→ P6 → P9 → Q1**。B は上表の通り不採。

配布（1.0）は C を hard predecessor に持つが、その C が 0.1.0 で済むため「配布は始まったが安全化は未了」の順序事故は最初から起きない。showcase / dev-docs 全テンプレートは既に minijinja 表現可能圏（parity 実測で確認）に収まっており、0.1.0 から minijinja で回る。

### C のエンジン候補と検証（spike 実施済）

判定基準: **テンプレートに渡るデータが host 言語のリフレクション / capability への経路を運ぶか**。実射結果:

| 候補 | 系統 | 評価（spike 済） |
|---|---|---|
| **python-liquid** | non-evaluating が言語仕様 | 呼び出し構文が host allowlist（filter/tag）のみ ＝ **安全がバインディング非依存**。注入した capability オブジェクトすら *呼べない*。helper は filter/context-aware filter/custom tag で全表現可（実証）。エスケープは `OutputNode.render_to_output` の override（~10行、実証）。macro 無し／`groupby`・`format`・文字列×n 無し ＝ 移行時にテンプレ logic をクエリ・custom filter へ押し出す（現テンプレでの要手当ては 3 箇所のみ、いずれも「テンプレに漏れた logic」） |
| **minijinja (`minijinja-py`)** | 閉じた値モデル（Rust） | 評価器は Rust、素データは Rust `Value` に marshal され Python 不在 ＝ dunder 経路は**構造封鎖**。**ただし RCE 閉包は dunder だけの必要条件で不十分** — 渡したオブジェクトの**非 `_` 属性・メソッド・非 `_` 名 global** は露出し呼べる（`x.pub.getcwd()` / `render_to_file()` 実行を確認）。よって安全は**境界の marshal 契約**（下記）。Jinja 互換で書き直し最小（macro native・`env.finalizer` フックあり・`{% render %}` は filter 化）。エラーは最厚（前後行＋キャレット＋変数）で LLM 執筆に有利 |
| 小さな自作評価器 | logic-less / 許可リスト | 言語は安全にできるが、真に難しい**コンテキスト別エスケープ**（`finalize`/`Markup`/whitespace）を再オープンする。不採 |

二択の軸: **liquid＝言語で構造保証（未信頼テンプレを既定安全で build する世界）／ minijinja＝ほぼ drop-in ＋ marshal 契約（自作・半信頼の世界）**。

**決定（P6）: minijinja 採用。** 決め手は移行コストの少なさ（macro 0・Jinja 互換・`finalizer` あり）と LLM 執筆性（Jinja系の訓練データ相続）。安全は言語構造保証（liquid）ではなく **marshal 契約**で確保し、その構築を P9 として engine 差し替え（P6）から分離する。liquid は「未信頼テンプレを既定安全で build する」へ倒す場合の対抗案として残す。

### minijinja を選ぶ場合の安全規律（marshal 契約）

minijinja は dunder は構造封鎖するが、**渡したオブジェクトの非 `_` グラフは全開**（属性・メソッド・その戻り値を辿れる）。安全は「テンプレートに live capability を到達させない」契約で、次で機械化する:

- **`_` 接頭辞境界**: minijinja は `_` 属性・`_` メソッドを既定で拒否（"insecure method call"）。another-mood は構造参照（`_parent`→木全体、`_meta`→アンカー戦略、`_children`）を既に `_` 予約接頭辞に置いており、**minijinja の `_` ブロックと一致 → 参照グラフは不可視**（テンプレは `_` フィールドを直接触っていない＝壊れない）。navigation は filter が Python 側で行う。
- **唯一の構築時ガード**: `MappingNode`/`ArrayNode`（＝dict/list 派生）の内容は minijinja が map/seq の items として露出する。ゆえに **composer の単一構築点で「値・要素は primitive か Node のみ」を再帰 assert**。型 `TemplateValue = primitive | Markup | Node | Mapping | Sequence` で pyright を一次ガードに。
- **globals 衛生（地雷）**: `_` 接頭辞は**属性は守るが global 名は守らない**。`env.globals[PROCESSOR_KEY]`（`"_render_processor"`）は `_` 名でも露出し、`.engine.render_to_file(...)` という**非 `_` メソッドでファイル書込 capability が開く**（実証）。→ globals は純粋 callable のみ。**`{% render %}` の filter 化で processor は closure に captured され global から消える**（minijinja は closure 変数を触らせない）＝この設計判断が安全にも効く。
- **CI 回帰テスト**: `{{ x.__class__… }}` / `{{ node.非_メソッド() }}` / `{{ operational_global.… }}` を実 render に撃ち無害を assert（値モデル＋オブジェクト集合＋globals が閉じたままかを守る）。

残る恒久義務は「非 `_` に capability を置かない」＋「globals は純粋 callable」の2点で、`_` 規約と render=filter が大半を肩代わりする。

### 移行コスト・エラー品質・執筆性（spike 実施済）

engine 選定の副次軸。安全軸（上）とは直交だが、二択の実コストを埋める。

- **移行難度（現 showcase + dev-docs 14 テンプレ走査）**: macro 使用 **0**。`{% filter under_heading %}` ブロック（~10）は pipe 化（`… | render | under_heading`、望ましい方向）。大半は機械置換。Liquid で真に手当てが要るのは **3 箇所のみ** ── `groupby`（→クエリ `grouped` へ）、`"#" * depth` の文字列反復（→custom filter）、`'%02d' | format`（→custom filter）── いずれも「テンプレに漏れた logic」＝ logic-less 規律が元々外へ出したいもの。minijinja は Jinja 互換ゆえ演算子（`~`/`//`/三項）がそのまま通り機械置換すら不要で、手当ては exotic filter 整備のみ。
- **エラー品質 / LLM 執筆性**: 記法誤りへのエラーは minijinja / liquid とも現行 jinja2 を上回る（キャレット＋前後行＋列、構造化フィールドで Diagnostic 化可）。minijinja が最厚（参照変数まで）。Stack Overflow 質問数は Jinja系（DTL + Twig + Jinja ≈ 40k）が Liquid（≈4k）の約10倍で、**minijinja は Jinja 構文ゆえこの執筆性を相続**する。Liquid は下位だが `{{ }}`＋`{% %}` の視覚的家族を共有し、罰は方言限定・loud で回収可能。逆に Liquid の strict さは LLM を安全/移植圏へ**自己強制**する guardrail（minijinja は非 `_` メソッド等の逸脱を静かに許す）。
- **移植性**: 単一 Python ツールには概ね畑違い。唯一の具体シナリオ＝ブラウザ / WASM プレビューでは minijinja が Rust→WASM で**同一 engine**（最高忠実度）、Liquid は python-liquid ＋ LiquidJS の別実装になる。

### 1.0 設計オプション: dual-mode（VS Code Workspace Trust 相当）

C 導入時、単純な全面 C 化ではなく **デフォルト non-evaluating（C＝安全、共有テンプレを無警戒に build してよい）／ ユーザが明示的に「信頼」した自作プロジェクトのみ評価エンジン（A の全 Jinja2 パワー）を opt-in で解禁**、という二段構えが可能。ローカル著者の表現力を殺さず配布のデフォルトを安全にできる。

これは VS Code Workspace Trust のアーキテクチャそのもの。留意点: Workspace Trust の**意味のある半分は Restricted Mode（= C）**で、同意プロンプト単体は Restricted フォールバックが無ければ CLI / MCP では theater（非対話の CI / MCP に人間の同意が無く、barrier にならない）。ゆえに dual-mode は C が実在して初めて成立する。コスト: エンジン2系統の保守。

### DoS はホスティング時に別レイヤで

C（および B）が閉じるのは RCE であって DoS ではない。`"x" * 10**12`（メモリ爆弾）や `{% for %}` 無限ループは言語レベルの許可リストを通る（乗算は `"  " * depth` 等で正当に使われ禁止できない）。リソース / 出力サイズ上限 ＋ プロセス隔離は、**無人 / ホスト build を導入するマイルストーン**で入れる。それまでは accepted risk（ローカル CLI ではハングを Ctrl-C で受けられる）。トリガー: ホスト / 無人 build の導入。
