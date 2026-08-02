# Template Trust Model

テンプレートエンジンの信頼境界 — 「誰が書いたテンプレートを、誰の手元で実行するか」— の設計。`build` / `watch` はプロジェクトのテンプレートを評価するため、この境界 — テンプレートが host のコードに届きうるか — が製品の安全性を規定する。

## External Design

### 信頼モデル: テンプレートは閉じた値モデルで評価する（RCE 構造封鎖）

テンプレートは **minijinja（閉じた Rust 値モデル）＋ marshal 契約**の上で評価する。テンプレートが触れるのは host 言語のリフレクション / capability への経路を持たない値だけ — ゆえに **build / watch で第三者のプロジェクトを走らせても任意コード（RCE）は走らない**。

- dunder 経路は minijinja が構造封鎖する
- 非 `_` 属性・メソッド・globals は marshal 契約が封じる（機構は Internal Design）
- この閉包は SSTI 回帰テストが実 render で実証・固定している

ゆえに `make` / `npm install` / Jekyll 型の「build = コードを走らせる」契約とは異なり、テンプレートを安全なコンテンツとして扱える。**`docs/` に RCE の危険注記は置かない** — RCE が閉じている以上、注記は過剰警告になる。

残る攻撃面は **DoS**（`"x" * 10**12` 等のメモリ爆弾・`{% for %}` 無限ループ）のみで、ローカル CLI では Ctrl-C の accepted-risk。リソース上限は無人 / ホスト build を導入するマイルストーンで入れる（[Proposals](#proposals) の DoS 節）。

### 背景: 信頼境界の二択

信頼境界の設計は本質的に次の二択:

| 望む世界 | 設計 |
|---|---|
| **「build = コードを走らせる」と理解させる**(ビルドツールとして正直に立つ) | **素の評価エンジン ＋ 危険注記**。untrusted build は OS / コンテナ隔離で守る。言語は不変 |
| **「テンプレは安全なコンテンツ、知らない人が無警戒に build してよい」を維持** | **non-evaluating エンジン**。知覚を「安全なコンテンツ」に保つには実態もそう作る |

採ったのは後者。中間形態を含めた比較検討は Internal Design を参照。

### 背景: 実行ベクタはテンプレートのみ

ソース4種のうち host コードへの経路を持ちうるのはテンプレートだけ（それも閉じた値モデルで封鎖）で、他3種はそもそも経路を持たない:

- **`contents/` (data)** — data 値は md output format の finalize で escape される（[anchor-spec.md](20-anchor-spec.md) の unsafe トラストモデル参照）
- **`definition/schema.yaml`** — 宣言的な型定義
- **`definition/views/`** — 境界付きの宣言 DSL（`from`/`flatten`/`join`/`where`/`grouped`/`select`/`sort`）。`where` 述語は演算子の閉じた enum（`EQ`/`GT`/`STARTSWITH`/`CONTAINS` 等）を `and`/`or`/`not` で結合するだけで、フィールド参照は dotted-key lookup（Python の `getattr` ではない）。`eval`/`exec`/式言語は無い（[record_predicate.py](../../../../src/another_mood/components/shared/record_predicate.py)）

ゆえに防御は**テンプレート評価の一点**（engine の閉じた値モデル ＋ marshal 契約）に集約してよい。

### 背景: unsafe HTML の信頼前提との整合

[anchor-spec.md](20-anchor-spec.md) の raw HTML（`unsafe=true`）は「著者は既にソースとテンプレートの全権を持つため escalation にならない」＝**著者 = 実行者**を前提に組まれている。これは著者が自分のプロジェクトに埋める HTML の話で、RCE 封鎖とは別レイヤ:

- unsafe HTML は「著者が自分の *出力* に責任を持つ」**表現力**の問題
- marshal 契約は「テンプレートが host の *コード* に届かない」**実行安全**の問題

**著者 ≠ 実行者**（第三者が配布プロジェクトを build）のケースは、RCE が閉じたぶん「build = コード実行」契約より安全 — これが non-evaluating エンジンを採る意義そのもの。残る差は「著者が unsafe HTML で書いた出力を第三者が信じるか」という *出力の信頼* で、実行安全とは独立に扱う。

## Internal Design

### 背景: なぜ SandboxedEnvironment を採らないか（穴が N 個ではなく根が 1 個）

Jinja2 の SSTI 経路（`{{ ''.__class__.__mro__[1].__subclasses__() }}` の直接記法、`| attr('__class__')`、`| map(attribute='__class__...')` 等）は**独立した N 個の欠陥ではなく、単一の根から生えている**:

> Jinja2 の値モデルは「Python オブジェクトをリフレクションで触る」。全 Python オブジェクトは `__class__` を持ち、そこからオブジェクトグラフ全体（`os` / `subprocess`）へ到達できる。

したがって:

- **`SandboxedEnvironment`（Jinja2 の実行時サンドボックス）は実行時ブロックリスト** — 危険属性を都度「禁止」する。禁止漏れの属性パスが見つかるたびに脱出 CVE が出る、後手のイタチごっこ。しかも DoS 等は塞がず偽の安心を生む
- **穴を個別に塞ぐ発想も同じ轍** — `attr`/`map(attribute=)`/`selectattr`/`groupby` は string 属性名でリフレクションへ迂回でき、しかもこれらは showcase で属性ソート等に広く使われる load-bearing なフィルタ。フィルタごと禁止できず、許可リスト側で「属性文字列を安全なリテラルに制約」する必要がある

正しい対処は値モデルを叩くことではなく、**値モデルが構造的に安全なエンジンへ移す**か、**プロセス / OS 隔離**でビルドごと囲うか。External Design の二択に中間形態（実行時サンドボックス）が無いのはこのため — 言語を縛るが漏れる／隔離もしない、の両世界で中途半端になる。

採ったのは前者で、`Environment` は minijinja（[template_engine.py](../../../../src/another_mood/components/generator/template_engine.py) の `make_environment`）。RCE は minijinja の値モデル ＋ marshal 契約で閉じ、DoS 対策（隔離 / リソース上限）はホスト / 無人 build のマイルストーンに送る。

### 背景: エンジン選定 — minijinja（spike 実測）

判定基準は **テンプレートに渡るデータが host 言語のリフレクション / capability への経路を運ぶか**。spike で 3 候補を実射した。

**python-liquid** — non-evaluating が言語仕様:

- 呼び出し構文が host allowlist（filter/tag）のみ ＝ **安全がバインディング非依存**。注入した capability オブジェクトすら *呼べない*
- 一方 macro 無し、`groupby`・`format`・文字列反復も無し ＝ 移行時にテンプレ logic をクエリ・custom filter へ押し出す必要がある（spike 時点の全テンプレ走査で要手当ては 3 箇所、いずれも「テンプレに漏れた logic」）

**minijinja（`minijinja-py`）** — 閉じた値モデル（Rust）:

- 評価器は Rust、素データは Rust `Value` に marshal され Python 不在 ＝ dunder 経路は**構造封鎖**
- **ただしそれだけでは RCE 閉包に不十分** — 渡したオブジェクトの非 `_` 属性・メソッドと global は露出し呼べる（下の露出規則）。安全は**境界の marshal 契約**に懸かる
- Jinja 互換で書き直し最小（macro native・`env.finalizer` フックあり）。エラーは最厚（前後行＋キャレット＋参照変数）

**小さな自作評価器** — logic-less / 許可リスト:

- 言語は安全にできるが、真に難しい**コンテキスト別エスケープ**（`finalize`/`Markup`/whitespace）を再オープンする。不採

残る二択の軸は「**liquid ＝ 言語で構造保証**（未信頼テンプレを既定安全で build する世界）」対「**minijinja ＝ ほぼ drop-in ＋ marshal 契約**（自作・半信頼の世界）」。

**決定: minijinja 採用。** 決め手:

- **移行コスト最小** — macro 使用 0・Jinja 互換（演算子 `~`/`//`/三項もそのまま通る）・`env.finalizer` フックあり
- **LLM 執筆性** — Jinja 系の訓練データを相続（Stack Overflow 質問数で Jinja 系 ≈ 40k、Liquid ≈ 4k の約 10 倍）
- **エラー品質** — minijinja / liquid とも jinja2 を上回る（キャレット＋前後行＋列、構造化フィールドで Diagnostic 化可）が、minijinja が最厚
- **移植性** — ブラウザ / WASM プレビューを作る場合、minijinja は Rust→WASM で**同一 engine**（最高忠実度）。liquid は python-liquid ＋ LiquidJS の別実装になる

安全は言語構造保証（liquid）ではなく marshal 契約で確保する。liquid は「未信頼テンプレを既定安全で build する」へ倒す場合の対抗案として残す。

### minijinja の露出規則（SSTI 回帰テストで pin）

minijinja がテンプレートに露出するのは、渡した値の **非 `_`・非 dunder のメンバ**（属性・メソッド）と container の items。実測で確定した規則:

- **dunder（`__class__` 等）**: 構造封鎖（undefined）。dot 記法・subscript とも。`attr` / `map(attribute=)` / `selectattr` / `groupby` の string 属性名経由でも同じ
- **`_` 接頭辞の属性・メソッド**: 既定で拒否（"insecure method call"）。**dict/list 派生かは無関係、純粋に `_` の有無**。データツリーの内部リンク（`_parent` / `_meta` / `_children()`）をテンプレートから遮断し、marshal されていない素の Python オブジェクト（`_NodeMeta`）へ歩き出せないのはこれによる
- **非 `_` の属性・メソッド**: 露出し、**呼べる**。戻り値もさらに辿れる
- **container items**（dict 値 / list 要素）: map/seq として露出
- **globals**: `_` ブロックは**属性は守るが global 名は守らない** — `_` 名で登録した global も丸見えで、メンバを辿って呼べる。ゆえに engine が global に登録するのはテンプレートヘルパーのみ（filter は独立の名前空間にあり、値として拾えない）
- **loader**: テンプレートが *path* を選ぶ唯一の場所（`include` / `extends` / `import` / `render` filter）だが、`../` も絶対 path も解決しない ＝ template ディレクトリ内に閉じる

さらに marshaling には **convert / wrap の非対称**がある:

- **スカラー（str/int/float/bool/None）は minijinja ネイティブ型へ*変換*（convert）**され、Python のメンバは越境しない。minijinja 独自の string メソッドの `format` は属性 traversal を持たず、`format_map` は存在しない ＝ `str.format` 反射経由の format-string SSTI は不成立
- **オブジェクト（dict/list 派生を含む）は*wrap***され、Python メソッドが漏れる
- ゆえに危険は「wrap される非スカラー（オブジェクト）経由で非 `_` capability に届く」経路に限られる
- `Markup` は convert 側: `__html__` / `unescape` / `striptags` 等の Python メンバは越境しない。一方 `env.finalizer` は Python 値を見るため、エスケープ免除の役目は保たれる

この規則は engine の側にあり、将来版で変わりうる。ゆえに **[test_ssti.py](../../../../tests/components/generator/test_ssti.py) が古典 SSTI payload を実 render に撃って pin する**。固定するのは両方向 — 封鎖側（上記の sealed 各項）と、設計上の露出側（非 `_` メンバ呼び出し・global 非保護 ＝ marshal 契約が前提とする 2 つのハザード）。露出側が赤になったら侵害ではなく engine の厳格化の合図で、契約を緩められる可能性を意味する。

### marshal 契約 ── テンプレに渡る値を型・構造で inert に閉じる

信頼モデルは「テンプレが触れる値に host capability への経路が無い」ことに懸かる。だが minijinja は渡した値の非 `_`・非 dunder メンバと container items を露出し呼べるようにする（上の露出規則）。しかも**任意 Python オブジェクトの安全性は動的に確認できない** — `__getattr__` / instance 属性 / ABC 登録で内省を欺けるので `dir()` 監査は後手。

ゆえに契約は runtime 検査ではなく、**型と構造でツール側コードの規律を保つ**問題として解く。露出する二系統を各々閉じる:

- **(a) データ**: inert 値モデル `InertValue = str|int|float|bool|None|InertMapping|InertArray` で閉じる。`load_model`（`Any`）由来の木を `ensure_inert` が検証・詰め替え（parse, don't validate）、`MappingNode`/`ArrayNode` が Inert container を継承してアンカーを足す。
    - **Inert container は構築後 read-only**: dict / list の mutator は明示的に raise する（静かな no-op にはしない）。露出規則の wrap 側で非 `_` メソッドはテンプレートから呼べ、木はビルド全体で共有されるため、mutator が生きていると別ページのデータ破壊と「テンプレに渡る値は inert」不変条件の破れを許してしまう
- **(b) filters/globals の戻り値**: エンジン所有の受け入れ列挙 `TemplateSafe = InertValue | Node | Markup | MissingNode` で閉じる。

設計の要点:

- **container は exact-type／スカラーは正規化、の非対称**:
    - container は **wrap** され Python メソッドが漏れるので、`type(v) in {InertMapping, InertArray, MappingNode, ArrayNode}` の exact-type 判定で敵対的サブクラスを弾く（`isinstance` 不可。`@final` は無料の静的表明）
    - スカラーは **convert** されメンバが届かないので、`isinstance` で受理し exact 型へ正規化する（安全な `str` サブクラスを誤って弾かないため）
- **`TemplateSafe` は基底でなく列挙**: 受け入れ要件は継承で表せない（派生すれば capability を足せる）ので、各具体型を列挙する:
    - **受け入れ側 `template_safe` が所有しエンジンだけが参照**。生産者は自分の具体戻り型（`Node | MissingNode` 等）を正直に宣言するだけ ── 消費者→生産者の一方向 import ∴ cast も循環も生じない
    - minijinja の undefined は `None` として届き、`pluck` / `to_yaml` は `None` を返す（`Undefined` 型は列挙に無い）
    - 副作用 callable は原則禁止。`render` filter のみ例外（戻り値 `Markup`、書込 capability は closure captured）

強制のレイヤ（① データ inert / ② foreign 属性不可 / ③④ 非 `_` メソッド・危険 dunder 不可 を担保）:

- **pyright（静的）**: inert container の `[InertValue]` parametrize と、filters/globals 戻り型のエンジン境界照合
- **render 境界ガード（runtime）**: `_bind` が各 binding を `ensure_template_safe` に通し、「テンプレに渡るのは `TemplateSafe` だけ」を入口一点で強制する（engine 所有の非 inert メンバは素通し、data は `ensure_inert` へ、それ以外は raise）。一様性のため内蔵 render も同じ境界を通る。①は加えて `ensure_inert` の exact-type 構築検証が担保
- **surface-audit テスト**: `TemplateSafe` 各型を MRO 全域で監査する — 非 `_` 表面が参照形（container = 素 dict/list、`MissingNode` = 宣言 field で各値 inert）に一致すること、foreign 属性を植えられないこと（`__slots__`/frozen）、body に想定外 protocol dunder（`__getattr__`/`__getitem__`/`__call__`）が無いこと。`Markup` は convert 側で表面が越境しない（上の露出規則で pin 済み）ため対象外
- **SSTI 回帰テスト（[test_ssti.py](../../../../tests/components/generator/test_ssti.py)）**: 上の 3 レイヤが前提とする engine 側の露出規則そのものを実 render で pin（前節）
- **残余**: `__slots__` 除去等は behavioral テストが捕まえるが、**監査テスト自体の削除は型でもテストでも防げず code review が担う**

## Proposals

未実装。1.0 の配布 / 共有機能に向けて詰める。

### DoS はホスティング時に別レイヤで

non-evaluating エンジン（また実行時サンドボックスも）が閉じるのは RCE であって DoS ではない。`"x" * 10**12`（メモリ爆弾）や `{% for %}` 無限ループは言語レベルの許可リストを通る（乗算は `"  " * depth` 等で正当に使われ禁止できない）。

リソース / 出力サイズ上限 ＋ プロセス隔離は、**無人 / ホスト build を導入するマイルストーン**で入れる。それまでは accepted risk（ローカル CLI ではハングを Ctrl-C で受けられる）。トリガー: ホスト / 無人 build の導入。
