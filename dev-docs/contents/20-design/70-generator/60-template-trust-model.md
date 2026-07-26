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

**決定: 0.1.0 から C（minijinja ＋ marshal 契約）。** 当初は A@0.1.0（注記のみ）→ C@1.0 の段階論だったが、C の実測軽量さ（[背景節](#external-design)）ゆえ前倒しした。C は **P6（engine 差し替え）＋ P9（marshal 契約の型・構造）＋ P11（SSTI 回帰テスト）**で構成し、全て phase 14（Q1 = 0.1.0 公開の前）。**P9 は純 Python で P6 非依存**（型・構造ロックの先行実装）、**P11 は minijinja の実 render が要り前提 P6**。依存の鎖は **P7（render filter 追加）→ P8（タグ廃止）→ P6**、P9 は並行、**P11 は P6 の後**、Q1 は P6・P9・P11 の後。B は上表の通り不採。

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

### marshal 契約（spike 実測で確定）

#### minijinja の露出ルール

minijinja がテンプレートに露出するのは、渡した値の **非 `_`・非 dunder のメンバ**（属性・メソッド）と container の items。実測で確定した規則:

- **dunder（`__class__` 等）**: 構造封鎖（undefined）。
- **`_` 接頭辞の属性・メソッド**: 既定で拒否（"insecure method call"）。**dict/list 派生かは無関係、純粋に `_` の有無**。
- **非 `_` の属性・メソッド**: 露出し、**呼べる**（dict 派生に生やした `danger()` が `os.getcwd()` を実行）。戻り値もさらに辿れる。
- **container items**（dict 値 / list 要素）: map/seq として露出。
- **globals**: `_` ブロックは**属性は守るが global 名は守らない** — `_render_processor` は `_` 名でも丸見えで `.engine.render_to_file("p")` が実際にファイルを書いた。

marshaling は **convert / wrap の非対称**: **スカラー（str/int/float/bool/None）は minijinja ネイティブ型へ*変換*される**（Python の str メソッドではなく minijinja 独自の string メソッドが露出する — `format`/`upper` 等は在るが、その `format` はフィールドに属性 traversal を持たず（`"{0.__class__}"` は「引数が見つからない」）、Python 専用の `format_map` も無い ＝ `str.format` 反射経由の format-string SSTI は不成立）。**オブジェクト（dict/list 派生を含む）は*wrap*される**（Python メソッドが漏れる）。ゆえに危険は「wrap される非スカラー（オブジェクト）経由で非 `_` capability に届く」経路に限られる。

#### 動的検査ではなく「閉じた構築路＋型ロック」

**任意の Python オブジェクトが安全かを動的に確認するのは不可能**（Python の値モデルは開いていて `__getattr__`/`__getattribute__`/instance 属性/ABC 登録で内省を欺ける — `dir()` 監査は SandboxedEnvironment のブロックリストと同じ後手）。ゆえに marshal 契約は「テンプレートの攻撃を実行時に弾く」ではなく、**ツール側コードの規律を型と構造で保つ**問題として解く:

- **単一入口**: ユーザテンプレートに渡る*データ*は generator の `build_node_map(load_model(...))` 一点。`load_model` は逆シリアライザなので産物は inert（live capability を*作れない*）。ここが自明性の根で、各変換が inert を保存すれば出力の inert さは帰納で従う。もう一系統は curated な filters/globals（小さな手書き集合）。
- **二段の型ロック**: (a) テンプレに渡る*データ*は inert 値モデル（`InertValue`）で閉じる、(b) filters/globals の戻り値は **`TemplateSafe`（エンジン所有の受け入れ列挙）** で閉じる。下記。
- **本番ビルドは値の安全性を動的検査しない**（主機構は型＋テスト）。`ensure_inert` の詰め替え検証だけが唯一の runtime 検証で、`Any` 源を exact-type で弾く narrow なもの。

#### inert 値モデル ── テンプレに渡るデータの型（`InertValue`）

データツリーは `load_model`（`Any`）由来なので、型を*正直*に保つ鍵は **検証を持つ container へ値を詰め替える**こと（parse, don't validate を型にする）:

```python
type InertValue = str | int | float | bool | None | InertMapping | InertArray
class InertMapping(dict[str, InertValue]):       # アンカー無しの inert container（基底）
    __slots__ = ()
class InertArray(list[InertValue]):
    __slots__ = ()
class MappingNode(InertMapping, Node):            # ＋ アンカー（_parent/_segment/_meta）
    __slots__ = ("_parent", "_segment", "_meta")
class ArrayNode(InertArray, Node):
    __slots__ = ("_parent", "_segment", "_meta")
```

marshal（`ensure_inert`）と anchoring（`wrap_tree`）は分離: `ensure_inert` が `Any` 境界で木を検証・詰め替え、`wrap_tree` は詰め替え済み inert ツリーを受けてアンカー（MappingNode/ArrayNode）を付ける。

| 要件 | 手段 |
|---|---|
| ① container が非 InertValue を保持しない | **`ensure_inert` の構築検証**: 各葉を **exact-type** で分岐 ── スカラー（str/int/float/bool/None）はそのまま、dict/list は Inert* へ変換（再帰）、それ以外は raise。`Any` 源に対する唯一の runtime 検証 |
| ② 非 `_` 属性を持てない（`self.pub=os`） | **`__slots__`**（`Node` 含む全基底に宣言 — 一つ欠くと `__dict__` 復活） |
| ③④ 非 `_` メソッド・危険な dunder override を持たない | **surface-audit テスト1本**: 4型（InertMapping/InertArray/MappingNode/ArrayNode）の非 `_` 表面 == 素 dict/list ＋ body に想定外 dunder 無し を assert |

- **exact-type（`isinstance` ではない）**: 許容 container を `type(v) in {InertMapping, InertArray, MappingNode, ArrayNode}` で判定。`isinstance` だと敵対的サブクラスを通す（minijinja が wrap し非 `_` メソッドが漏れる）。exact-type ゆえサブクラスは構築点で悉く弾かれ、`@typing.final` は静的 no-subclass 表明として無料で残す。
- **④「危険 dunder」の実体は body での protocol dunder override**: minijinja は `__class__` 等の dunder を構造封鎖する（上記露出ルール）ので、危険は dunder が*見える*ことではなく、minijinja が render 中に invoke する protocol dunder（属性アクセス / `__getitem__` / `__call__`）を我々の body が override して非 inert 値を返すこと。surface-audit はこれを MRO 全域で監査するため、`Node` や sub-class 裏に紛れた foreign base の dunder も捕える。

#### `TemplateSafe` ── 型ではなく、エンジンが所有する受け入れ列挙

**`TemplateSafe` は型ではない**。filters/globals がテンプレに露出してよい**具体型の whitelist に名を付けた union alias** にすぎない。

- 受け入れ要件（capability-free な表面・exact-type）は**継承で表現できない性質** ── どんなクラスも派生させれば非 `_` メンバや capability を足せて Safe でなくなる（だから `ensure_inert` も `type(v) in {...}`）。「TemplateSafe を継承する基底」は作れず、**受け入れ可能な各具体型を列挙する**しかない。各メンバは `TemplateSafe` の派生ではなく、列挙された要素。
- whitelist は**受け入れる側（テンプレートエンジン）が所有し、エンジンだけが参照する**。**生産者（filters/globals を書くモジュール）は `TemplateSafe` を参照しない** ── 各生産者は自分の具体戻り型（`Node | MissingNode` / `Markup` / `InertValue | Undefined` 等）を正直に宣言するだけ。「安全か」は生産者が型で主張するものではなく、境界でエンジンが下す判定。
- 列挙: `TemplateSafe = InertValue | Node | Markup | MissingNode | Undefined`。エンジンが各メンバを**それぞれの住処から import** する（`InertValue`←inert / `Node`←data_tree / `MissingNode`←data_tree_filters / `Markup`←markupsafe / `Undefined`←jinja2）。**消費者→生産者の一方向 import** ゆえ循環しない（生産者はエンジンを import しないため）。
    - `MissingNode` は生産者 data_tree_filters に**据え置く**（値型を「土台」へ動かす必要はない ── whitelist が生産者の型を列挙するだけ）。
    - `Undefined`（欠損 lookup の sentinel、finalize で `""`）は capability-free な露出値なのでメンバ。これは現行 jinja2 前提の列挙で、engine 差し替え（P6）時に revisit。P9 の engine-independent は「差し替え前に着手可能」の意で、差し替え前に jinja2 を参照するのは妥当（要件自体が minijinja の露出仕様から逆算されている）。

**依存の向き（cast を生まない DAG）**: 具体値型・生産者（inert / data_tree / data_tree_filters / markupsafe / jinja2）を、`template_engine` が下向きに import して `TemplateSafe` を組み・境界で強制する。生産者側にもオーケストレーション側にも `-> TemplateSafe` 注釈や cast は現れない。cast が要る設計はこの依存の向きが歪んでいる兆候。

**強制**: エンジンの引数型 `filters/globals: Mapping[str, Callable[..., TemplateSafe]]`。生産者が組んだ正直型の filter マップをここへ渡す点で pyright が「各 filter の具体戻り型 ∈ 列挙」を照合する。`markdown_engine`（MD 束縛のエンジン構築）は filters を転送するため列挙を参照するが、生産者ではなく**エンジン部分系**なので generator でなくエンジン側に置く（`md ↔ template_engine` の循環を避け、`MD`＋`TemplateEngine`＋`TemplateSafe` を束ねる薄い専用モジュール）。

**副作用の例外**: 副作用 callable は原則禁止だが、`render` filter が唯一の sanctioned 例外。戻り値は `Markup` で、書込 capability は closure に captured されテンプレから到達不能（`_` 名 global 露出を render=filter 化が閉じる）。

#### 強制のレイヤと残余

- **pyright**（静的）: (a) inert container が `[InertValue]` で正直に parametrize、(b) filters/globals の具体戻り型がエンジン境界で列挙 `TemplateSafe` と照合。
- **構築検証**（runtime, 一度）: `ensure_inert` が exact-type で各葉を検証し木を Inert* へ詰め替え ── ①の担保。
- **surface-audit テスト**（一度）: 4型の非 `_` 表面＋body dunder を監査（`__slots__` の `__dict__` 抑止も pin）。素 dict/list の継承ビルトイン表面は露出・呼べるが inert な中身しか触らない capability-free として一度監査。
- **残余**: 構築検証・`__slots__` を外す編集は behavioral テスト（foreign 拒否／`__dict__` 抑止）が捕まえる。**surface-audit テスト*自体*の削除は型でもテストでも防げず**、code review が担う。

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
