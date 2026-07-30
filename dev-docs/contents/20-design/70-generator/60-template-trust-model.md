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
- **`definition/views/`** — 境界付きの宣言 DSL（`from`/`flatten`/`join`/`where`/`grouped`/`select`/`sort`）。`where` 述語は演算子の閉じた enum（`EQ`/`GT`/`STARTSWITH`/`CONTAINS` 等）を `and`/`or`/`not` で結合するだけで、フィールド参照は dotted-key lookup（Python の `getattr` ではない）。`eval`/`exec`/式言語は無い（[record_predicate.py](../../../../src/another_mood/components/shared/record_predicate.py)）

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

### marshal 契約 ── テンプレに渡る値を型・構造で inert に閉じる

信頼モデル C は「テンプレが触れる値に host capability への経路が無い」ことに懸かる。minijinja は渡した値の非 `_`・非 dunder メンバと container items を露出し呼べるようにする（前提の露出規則は Proposals「marshal 契約の前提」、実 render での pin は P11）。**任意 Python オブジェクトの安全性は動的に確認できない**（`__getattr__` / instance 属性 / ABC 登録で内省を欺けるので `dir()` 監査は後手）── ゆえに契約は runtime 検査でなく、**型と構造でツール側コードの規律を保つ**問題として解く。露出する二系統を各々閉じる:

- **(a) データ**: inert 値モデル `InertValue = str|int|float|bool|None|InertMapping|InertArray` で閉じる。`load_model`（`Any`）由来の木を `ensure_inert` が検証・詰め替え（parse, don't validate）、`MappingNode`/`ArrayNode` が Inert container を継承してアンカーを足す。
- **(b) filters/globals の戻り値**: エンジン所有の受け入れ列挙 `TemplateSafe = InertValue | Node | Markup | MissingNode` で閉じる。

設計の要点:

- **container は exact-type／スカラーは正規化の非対称**: minijinja は container を **wrap**（Python メソッドが漏れる）ので `type(v) in {InertMapping, InertArray, MappingNode, ArrayNode}` で敵対的サブクラスを弾く（`isinstance` 不可、`@final` は無料の静的表明）。スカラーは **convert**（ネイティブ型化）でメンバが届かないので `isinstance` 受理＋exact 型へ正規化（安全な `str` サブクラスを誤って弾かないため）。
- **`TemplateSafe` は基底でなく列挙**: 受け入れ要件は継承で表せない（派生すれば capability を足せる）ので各具体型を列挙。**受け入れ側 `template_safe` が所有しエンジンだけが参照**、生産者は自分の具体戻り型（`Node | MissingNode` 等）を正直に宣言するだけ ── 消費者→生産者の一方向 import ∴ cast も循環も生じない。`Undefined` は engine 差し替え（P6）で列挙から消えた ── minijinja の undefined は `None` として届き、`pluck` / `to_yaml` は `None` を返す。副作用 callable は原則禁止、`render` filter のみ例外（戻り値 `Markup`、書込 capability は closure captured）。

強制のレイヤ（① データ inert / ② foreign 属性不可 / ③④ 非 `_` メソッド・危険 dunder 不可 を担保）:

- **pyright（静的）**: inert container の `[InertValue]` parametrize と、filters/globals 戻り型のエンジン境界照合。
- **render 境界ガード（runtime）**: `_bind` が各 binding を `ensure_template_safe` に通す ── 「テンプレに渡るのは `TemplateSafe` だけ」を入口一点で強制（engine 所有の非 inert メンバは素通し、data は `ensure_inert` へ、それ以外は raise）。一様性のため内蔵 render も同じ境界を通る。①は加えて `ensure_inert` の exact-type 構築検証が担保。
- **surface-audit テスト**: `TemplateSafe` 各型の非 `_` 表面が参照形（container=素 dict/list、`MissingNode`=宣言 field で各値 inert）に一致し、foreign 属性を植えられず（`__slots__`/frozen）、body に想定外 protocol dunder（`__getattr__`/`__getitem__`/`__call__`）が無いことを MRO 全域で監査。`Markup` は engine 露出方式依存 ∴ P11 へ。
- **残余**: `__slots__` 除去等は behavioral テストが捕まえるが、**surface-audit テスト自体の削除は型でもテストでも防げず code review が担う**。

## Proposals

未実装。1.0 の配布 / 共有機能に向けて詰める。

### 段階論: C を 0.1.0 から採る

信頼境界の選択肢は本質的に二択で、B は両世界で中途半端（言語を縛るが漏れる／隔離もしない）ゆえ不採:

| 望む世界 | 設計 |
|---|---|
| **「build = コードを走らせる」と理解させる**（ビルドツールとして正直に立つ） | **A ＋ untrusted build は OS / コンテナ隔離**。言語は不変、showcase もそのまま |
| **「テンプレは安全なコンテンツ、知らない人が無警戒に build してよい」を維持** | **C（non-evaluating エンジン）**。知覚を「安全なコンテンツ」に保つには実態もそう作る |

**決定: 0.1.0 から C（minijinja ＋ marshal 契約）。** 当初は A@0.1.0（注記のみ）→ C@1.0 の段階論だったが、C の実測軽量さ（[背景節](#external-design)）ゆえ前倒しした。C は **P6（engine 差し替え）＋ P9（marshal 契約の型・構造）＋ P11（SSTI 回帰テスト）**で構成し、全て phase 14（Q1 = 0.1.0 公開の前）。**P9 は純 Python で P6 非依存**（型・構造ロックの先行実装）、**P11 は minijinja の実 render が要り前提 P6**。依存の鎖は **P7（render filter 追加）→ P8（タグ廃止）→ P6**、P9 は並行、**P11 は P6 の後**、Q1 は P6・P9・P11 の後。B は上表の通り不採。

配布（1.0）は C を hard predecessor に持つが、その C が 0.1.0 で済むため「配布は始まったが安全化は未了」の順序事故は最初から起きない。showcase / dev-docs 全テンプレートは既に minijinja 表現可能圏（parity 実測で確認）に収まっており、0.1.0 から minijinja で回る。

### C のエンジン候補と検証（spike 実施済）

判定基準: **テンプレートに渡るデータが host 言語のリフレクション / capability への経路を運ぶか**。実射結果:

| 候補 | 系統 | 評価（spike 済） |
|---|---|---|
| **python-liquid** | non-evaluating が言語仕様 | 呼び出し構文が host allowlist（filter/tag）のみ ＝ **安全がバインディング非依存**。注入した capability オブジェクトすら *呼べない*。helper は filter/context-aware filter/custom tag で全表現可（実証）。エスケープは `OutputNode.render_to_output` の override（~10行、実証）。macro 無し／`groupby`・`format`・文字列×n 無し ＝ 移行時にテンプレ logic をクエリ・custom filter へ押し出す（現テンプレでの要手当ては 3 箇所のみ、いずれも「テンプレに漏れた logic」） |
| **minijinja (`minijinja-py`)** | 閉じた値モデル（Rust） | 評価器は Rust、素データは Rust `Value` に marshal され Python 不在 ＝ dunder 経路は**構造封鎖**。**ただし RCE 閉包は dunder だけの必要条件で不十分** — 渡したオブジェクトの**非 `_` 属性・メソッド・非 `_` 名 global** は露出し呼べる（`x.pub.getcwd()` / `render_to_file()` 実行を確認）。よって安全は**境界の marshal 契約**（下記）。Jinja 互換で書き直し最小（macro native・`env.finalizer` フックあり・`{% render %}` は filter 化済み [P8](node:/tasks/P/tasks/P8)）。エラーは最厚（前後行＋キャレット＋変数）で LLM 執筆に有利 |
| 小さな自作評価器 | logic-less / 許可リスト | 言語は安全にできるが、真に難しい**コンテキスト別エスケープ**（`finalize`/`Markup`/whitespace）を再オープンする。不採 |

二択の軸: **liquid＝言語で構造保証（未信頼テンプレを既定安全で build する世界）／ minijinja＝ほぼ drop-in ＋ marshal 契約（自作・半信頼の世界）**。

**決定（P6）: minijinja 採用。** 決め手は移行コストの少なさ（macro 0・Jinja 互換・`finalizer` あり）と LLM 執筆性（Jinja系の訓練データ相続）。安全は言語構造保証（liquid）ではなく **marshal 契約**で確保し、その構築を P9 として engine 差し替え（P6）から分離する。liquid は「未信頼テンプレを既定安全で build する」へ倒す場合の対抗案として残す。

### marshal 契約の前提: minijinja の露出ルール（spike 実測）

> 実装済みの marshal 契約（型・構造ロック）は Internal Design「marshal 契約」節を参照。本節はその契約が前提とする minijinja の露出規則で、engine 差し替え（P6）で現実になり、P11 が実 render で pin する。

minijinja がテンプレートに露出するのは、渡した値の **非 `_`・非 dunder のメンバ**（属性・メソッド）と container の items。実測で確定した規則:

- **dunder（`__class__` 等）**: 構造封鎖（undefined）。
- **`_` 接頭辞の属性・メソッド**: 既定で拒否（"insecure method call"）。**dict/list 派生かは無関係、純粋に `_` の有無**。
- **非 `_` の属性・メソッド**: 露出し、**呼べる**（dict 派生に生やした `danger()` が `os.getcwd()` を実行）。戻り値もさらに辿れる。
- **container items**（dict 値 / list 要素）: map/seq として露出。
- **globals**: `_` ブロックは**属性は守るが global 名は守らない** — `_render_processor` は `_` 名でも丸見えで `.engine.render_to_file("p")` が実際にファイルを書いた。

marshaling は **convert / wrap の非対称**: **スカラー（str/int/float/bool/None）は minijinja ネイティブ型へ*変換*される**（Python の str メソッドではなく minijinja 独自の string メソッドが露出する — `format`/`upper` 等は在るが、その `format` はフィールドに属性 traversal を持たず（`"{0.__class__}"` は「引数が見つからない」）、Python 専用の `format_map` も無い ＝ `str.format` 反射経由の format-string SSTI は不成立）。**オブジェクト（dict/list 派生を含む）は*wrap*される**（Python メソッドが漏れる）。ゆえに危険は「wrap される非スカラー（オブジェクト）経由で非 `_` capability に届く」経路に限られる。

### テンプレートからのデータツリー変更 (P13)

上の wrap 規則の帰結として、`InertMapping` / `InertArray` の dict / list mutator（`pop` / `clear` / `update` / `setdefault` / `append` / `sort` 等）はテンプレートから呼べ、**実際に Python 側のツリーを書き換える**（実測）。ノードはビルド全体で共有されるため、あるページのテンプレートが他ページのデータを壊せる。`dict.items` のような Python callable を木に植えることもでき、「テンプレに渡る値は inert」の不変条件も破れる。

**これは信頼モデル C の穴ではない**: 植えられるのはテンプレートから既に届く値（inert container のメソッド、global の closure）に限られ、新しい capability は得られない ── RCE ではなく**ビルド整合性**の問題。ゆえに 0.1.0 のブロッカーではない。**P12（pycompat 無効化）でも塞がらない**: pycompat が触るのは convert 側（ネイティブ文字列への後付けメソッド）で、mutator は wrap 側の素の属性 lookup。

塞ぎ方は `InertMapping` / `InertArray` に mutator を raise するメソッドとして定義する形。**公開名の集合は plain dict / list と同一のまま**なので、surface-audit テストの参照形は再設計不要で挙動だけが変わる。

**0.1.0 後に後追いで塞いでも互換性を保つ**と判断する。`docs/` に container のメソッド語彙の案内は無く、showcase / dev-docs / 内蔵メタテンプレートでの使用はゼロ。加えて mutation の可視範囲はレンダリング順序依存で、依存できる挙動になっていない ── 削除するのは仕様ではなく壊れ方。ただし塞ぐ実装は**静かな no-op ではなく明示的なエラー**でなければならない（気づけない別の壊れ方に置き換えては意味が無い）。

### SSTI 回帰テスト（P6 依存・別タスク）

上記の安全性は minijinja の露出セマンティクスに依存し、その pin は**実 render に撃つ回帰テスト**が担う。**現行 minijinja-py での実測は確定したが露出規則は将来版で変わりうる**ため「現行で安全、それを回帰テストで固定する」姿勢を採る。payload: dunder 直記法 / `attr('__class__')` / `str.format`・`format_map` の format-string 系 / `_` 名 global 露出 / 非 `_` メソッド dispatch（いずれも周知の古典で新規開示にはならない）。**minijinja を実行環境に入れる P6 まで走らせられない**ため、型・構造の先行実装（P9）とは別タスク（P11）に分ける。

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
