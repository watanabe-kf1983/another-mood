# Template Trust Model

テンプレートエンジンの信頼境界 — 「誰が書いたテンプレートを、誰の手元で実行するか」— の設計。`build` / `watch` はプロジェクトのテンプレートを**コードとして実行**するため、この境界が製品の安全性を規定する。

利用者向けの注意書き（`build` / `watch` の信頼契約）は `docs/` を参照。本仕様は設計判断に絞る。

## External Design

### 信頼モデル (0.1.0): プロジェクトを build する = そのプロジェクトのコードを走らせる

0.1.0 の立場は明示的に **「テンプレートは信頼された入力」**。`build` / `watch` はテンプレートを素の Jinja2 (`Environment`) で評価し、サンドボックス化しない。したがって悪意あるプロジェクトを build / watch すれば、その利用者のマシンで任意コードが走る。

これは `make` / `npm install` / Jekyll など**ビルドツールの標準契約**と同型で、脆弱性ではなく「ビルドツールはコードを走らせる」という性質。よって対策は言語のサンドボックス化ではなく、信頼できないプロジェクトを build しない運用（将来は [Proposals](#proposals) の隔離 / non-evaluating エンジン）で受ける。

`docs/` に置く信頼契約の注記（確定文面）:

> `mood build` and `mood watch` render a project's templates, which run as code on your machine — with no sandboxing, as with most build tools (`make`, `npm install`, Jekyll). A malicious project can therefore execute arbitrary code. Only build or watch projects you trust; do not run them on sources received from untrusted parties.

注記の設計判断:

- **主語は「プロジェクト / ソース」であって「データ」ではない** — このツールの語彙で「データ」= `contents/` は最も安全な部類（後述の通り escape される）。実行ベクタはテンプレートなので、「信頼できないデータ」と書くと読み手が「テンプレートだけ貰ったから安全」と真逆に誤読する
- **結果（任意コード実行）を一節で述べる** — 「secure でない」だけだと under-alarm する。深刻度を較正させる
- **ビルドツール群への並置で正規化する** — 締め出したい相手には新情報ゼロ（皆知る契約）。信頼して使うローカル著者を「特別に危険」と怯えさせず、免罪符でなく業界標準の正直なラベルに読ませる
- **exploit のレシピは書かない** — 契約（危険であること）は書くが、撃ち方は書かない

### 背景: 実行ベクタはテンプレートのみ

ソース4種のうち任意コード実行に至るのはテンプレートだけで、他3種は経路を持たない:

- **`contents/` (data)** — data 値は md output format の finalize で escape される（[anchor-spec.md](20-anchor-spec.md) の unsafe トラストモデル参照）
- **`definition/schema.yaml`** — 宣言的な型定義
- **`definition/queries/`** — 境界付きの宣言 DSL（`from`/`flatten`/`join`/`where`/`grouped`/`select`/`sort`）。`where` 述語は演算子の閉じた enum（`EQ`/`GT`/`STARTSWITH`/`CONTAINS` 等）を `and`/`or`/`not` で結合するだけで、フィールド参照は dotted-key lookup（Python の `getattr` ではない）。`eval`/`exec`/式言語は無い（[record_predicate.py](../../../../src/another_mood/components/shared/record_predicate.py)）

ゆえに注記・将来の防御はいずれも**テンプレート実行の一点**に集約してよい。

### 背景: unsafe HTML の信頼前提との整合

[anchor-spec.md](20-anchor-spec.md) の raw HTML（`unsafe=true`）の議論は「著者は既にソースとテンプレートの全権を持つため escalation にならない」＝**著者 = 実行者**を前提に組まれている。本仕様の RCE 議論は逆に**著者 ≠ 実行者**（配布されたプロジェクトを第三者が build する）を扱う。

両者は矛盾しない。上位の信頼モデル **「プロジェクトを build する = そのコードを走らせる = そのプロジェクトを信頼する」** の下では、unsafe HTML も任意コードも「信頼したプロジェクトの一部」として同じ傘に入る。anchor-spec の前提は 0.1.0（A）の信頼モデルそのものであり、著者 ≠ 実行者のケースは信頼契約の外側（＝ build すべきでない）として扱う。

## Internal Design

### 背景: なぜ SandboxedEnvironment を採らないか（穴が N 個ではなく根が 1 個）

Jinja2 の SSTI 経路（`{{ ''.__class__.__mro__[1].__subclasses__() }}` の直接記法、`| attr('__class__')`、`| map(attribute='__class__...')` 等）は**独立した N 個の欠陥ではなく、単一の根から生えている**:

> Jinja2 の値モデルは「Python オブジェクトをリフレクションで触る」。全 Python オブジェクトは `__class__` を持ち、そこからオブジェクトグラフ全体（`os` / `subprocess`）へ到達できる。

したがって:

- **`SandboxedEnvironment`（B）は実行時ブロックリスト** — 危険属性を都度「禁止」する。禁止漏れの属性パスが見つかるたびに脱出 CVE が出る、後手のイタチごっこ。しかも DoS 等は塞がず偽の安心を生む
- **穴を個別に塞ぐ発想も同じ轍** — `attr`/`map(attribute=)`/`selectattr`/`groupby` は string 属性名でリフレクションへ迂回でき、しかもこれらは showcase で属性ソート等に広く使われる load-bearing なフィルタ。フィルタごと禁止できず、許可リスト側で「属性文字列を安全なリテラルに制約」する必要がある

正しい対処は値モデルを叩くのではなく、**値モデルが構造的に安全なエンジンへ移す**（C）か、**プロセス / OS 隔離**でビルドごと囲う。0.1.0 は素の `Environment` のまま（[template_engine.py](../../../../src/another_mood/components/generator/template_engine.py) の `make_environment`）とし、防御層はエンジン成熟（C）とホスティング（隔離）に送る。

## Proposals

未実装。1.0 の配布 / 共有機能に向けて詰める。

### 段階論: A@0.1.0 → C@1.0

信頼境界の選択肢は本質的に二択で、B は両世界で中途半端（言語を縛るが漏れる／隔離もしない）ゆえ不採:

| 望む世界 | 設計 |
|---|---|
| **「build = コードを走らせる」と理解させる**（ビルドツールとして正直に立つ） | **A ＋ untrusted build は OS / コンテナ隔離**。言語は不変、showcase もそのまま |
| **「テンプレは安全なコンテンツ、知らない人が無警戒に build してよい」を維持** | **C（non-evaluating エンジン）**。知覚を「安全なコンテンツ」に保つには実態もそう作る |

段階論: **0.1.0 は A**（local / trusted 前提、注記のみ）。**1.0 で C**。C 移行は **untrusted なテンプレート配布を導入する 1.0 機能の hard predecessor** とし、「配布は始まったが安全化は未了」の順序事故を防ぐ（tasks.yaml に依存付きで登録する）。

### 0.x の制約: テンプレ表現を C 表現可能圏に留める

C（non-evaluating）に倒す以上、0.x の間に Jinja2 固有機能（任意メソッド呼び出し、drop で表現できない構文）を showcase / docs で育てると、1.0 が全テンプレート著者を巻き込む破壊的移行になる。

現状は安全側: showcase 全テンプレートを走査した結果、dunder アクセス 0、データオブジェクトへのメソッド呼び出し 0、関数呼び出しは全て curated なグローバル / フィルタ（`node`/`link`/`code_inline` 等）、`sort`/`map`/`selectattr` の属性引数は全て安全なリテラル。**既に drop ＋ curated helpers 様式（≒ Liquid 表現可能圏）に収まっている**。0.x では意識してこの圏内に留める。

### C のエンジン候補と検証（spike deferred）

| 候補 | 系統 | 評価（context7 一次調査） |
|---|---|---|
| **python-liquid** | non-evaluating が言語仕様 | 保証がバインディング非依存で原理的に最強。ただし Python 港の実像（カスタム tag/filter・drop・メンテ）は未検証 |
| **minijinja (`minijinja-py`)** | 閉じた値モデル（Rust） | Jinja2 互換構文で書き直し最小。**ただし README 明記「Python objects retain their APIs ... without an extra security layer」** — 安全性は境界での marshal 次第でタダではない。ネイティブ `{% include %}` あり（`{% render %}` 拡張の土台）、`minijinja-contrib` pycompat |
| 小さな自作評価器 | logic-less / 許可リスト | 言語は安全にできるが、テンプレートエンジンの真に難しい部分＝**コンテキスト別エスケープ**（`finalize`/`Markup`/whitespace）を再オープンする |

C 着手時に spike を1本撃つ: `{{ x.__class__ }}` / `{{ x.__class__.__mro__[1].__subclasses__() }}` / `{{ ""|attr("__class__") }}` / `{{ [x]|map(attribute="__class__")|list }}` を、このツールと同じデータ渡し方で (a) minijinja-py（データを ①素の dict ②ネイティブ marshal ③Object ラップ）(b) python-liquid に実射し、どれが構造的に弾くかを表にする。判定基準は一言: **テンプレートに渡るデータが host 言語のリフレクションへの経路を運ぶか**。

### 1.0 設計オプション: dual-mode（VS Code Workspace Trust 相当）

C 導入時、単純な全面 C 化ではなく **デフォルト non-evaluating（C＝安全、共有テンプレを無警戒に build してよい）／ ユーザが明示的に「信頼」した自作プロジェクトのみ評価エンジン（A の全 Jinja2 パワー）を opt-in で解禁**、という二段構えが可能。ローカル著者の表現力を殺さず配布のデフォルトを安全にできる。

これは VS Code Workspace Trust のアーキテクチャそのもの。留意点: Workspace Trust の**意味のある半分は Restricted Mode（= C）**で、同意プロンプト単体は Restricted フォールバックが無ければ CLI / MCP では theater（非対話の CI / MCP に人間の同意が無く、barrier にならない）。ゆえに dual-mode は C が実在して初めて成立する。コスト: エンジン2系統の保守。

### DoS はホスティング時に別レイヤで

C（および B）が閉じるのは RCE であって DoS ではない。`"x" * 10**12`（メモリ爆弾）や `{% for %}` 無限ループは言語レベルの許可リストを通る（乗算は `"  " * depth` 等で正当に使われ禁止できない）。リソース / 出力サイズ上限 ＋ プロセス隔離は、**無人 / ホスト build を導入するマイルストーン**で入れる。それまでは accepted risk（ローカル CLI ではハングを Ctrl-C で受けられる）。トリガー: ホスト / 無人 build の導入。
