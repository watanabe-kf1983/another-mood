# Template Trust Model

テンプレートエンジンの信頼境界 — 「誰が書いたテンプレートを、誰の手元で実行するか」— の設計。`build` / `watch` はsbdb プロジェクトのテンプレートを評価するため、この境界 — テンプレートが host のコードに届きうるか — が製品の安全性を規定する。

## External Design

### 信頼モデル: テンプレートは閉じた値モデルで評価する（RCE 構造封鎖）

テンプレートは **minijinja（閉じた Rust 値モデル）＋ marshal 契約**の上で評価する。テンプレートが触れるのは host 言語のリフレクション / capability への経路を持たない値だけ — ゆえに **build / watch で第三者が書いたsbdb プロジェクトを走らせても任意コード（RCE）は走らない**。

- dunder 経路は minijinja が構造封鎖する
- 非 `_` 属性・メソッド・globals は marshal 契約が封じる（機構は Internal Design）
- この閉包は SSTI 回帰テストが実 render で実証・固定している

ゆえに `make` / `npm install` / Jekyll 型の「build = コードを走らせる」契約とは異なり、テンプレートを安全なコンテンツとして扱える。**`docs/` に RCE の危険注記は置かない** — RCE が閉じている以上、注記は過剰警告になる。

残る攻撃面は **DoS** のみで、これはツールではなく build を走らせる側が OS 層で閉じる（下記 DoS 節）。

この選択に至った二択（素の評価エンジン ＋ 危険注記か、non-evaluating エンジンか）、実行時サンドボックスを中間形態として採らない理由、エンジン選定の spike は[背景](../../90-appendix/20-design/70-generator/25-template-trust-model.md)。

### 背景: 実行ベクタはテンプレートのみ

sbdb プロジェクトのソースのうち host コードへの経路を持ちうるのはテンプレートだけ（それも閉じた値モデルで封鎖）で、他はそもそも経路を持たない:

- **`contents/` (data)** — data 値は md output format の finalize で escape される（[unsafe HTML の信頼前提との整合](../../90-appendix/20-design/70-generator/25-template-trust-model.md#unsafe-html-の信頼前提との整合)参照）
- **`definition/schema.yaml`** — 宣言的な型定義
- **`definition/views/`** — 境界付きの宣言 DSL（`from`/`flatten`/`join`/`where`/`grouped`/`select`/`sort`）。`where` 述語は演算子の閉じた enum（`EQ`/`GT`/`STARTSWITH`/`CONTAINS` 等）を `and`/`or`/`not` で結合するだけで、フィールド参照は dotted-key lookup（Python の `getattr` ではない）。`eval`/`exec`/式言語は無い（`shared/record_predicate.py`）
- **`definition/reports.yaml` / `sbdb.yaml`** — 宣言的な設定

ゆえに防御は**テンプレート評価の一点**（engine の閉じた値モデル ＋ marshal 契約）に集約してよい。

### DoS 封じ込めは実行者の責務（ツールは非実装）

RCE はツールが構造で閉じる（上）。DoS は閉じない — 閉じるべき層がツールの外にあるため、ツールは何も実装しない。

- **単発の爆弾は minijinja が構造で拒む**。`range(n)` の要素数上限（10 万）とテンプレート再帰上限は採用版（minijinja 2.23.0）から、文字列・シーケンスの `*` 反復上限（1 億）は 3.x 系から閉じている。`"x" * 10**12` 型の一撃はもう通らない
- **残るのは累積・増幅**で、命令数ではなくバイト数で膨れる — 倍々連結（`ns.x ~ ns.x` を N 回で 2^N バイト）、フィルタ増幅（`| indent(巨大幅)` は小さな入力 × スカラー引数を巨大出力に。観測で入力 10 万バイト → 約 5GB）、データ列のネストループ。各段は合法サイズで総量だけが爆発する
- **fuel では閉じない**。minijinja の `fuel` は命令 1 個 = 1 の CPU 予算で確保バイト数を見ないため、上記のメモリ増幅は命令数が小さく素通りする。しかも fuel はセキュリティ境界に立たない — 必要な文脈（下記ホスト）では OS 隔離が CPU も一緒に縛るので冗長、不要な文脈（ローカル）では accepted risk。既定 ON はメモリを止めないのに上限があるように見え、誤った安心を配る ∴ 採らない
- **封じ込めは実行者が OS 層で行う**。**著者 = 実行者**（自分の / 選んで信頼したプロジェクトを自分の機械で build）では accepted risk — 自分のテンプレートの暴走で傷つくのは自分だけで権限昇格ではない。**著者 ≠ 実行者**（第三者の配布プロジェクトをホストで build）になった時点で、実行者が cgroup / コンテナ / `RLIMIT_AS` でプロセスを囲う。これはインフラ設定でツールのコードではなく、CPU・メモリ・時間を一括で縛る（`RLIMIT_AS` は確保要求自体を失敗させ、スラッシュや無作為な OOM-kill ではなく当該プロセスを決定的に落とす）。CI・各種ホスト build が例外なくそうしている場所
- **ローカル accepted risk の注意**: 巨大な単一確保は minijinja（C 拡張）内で走り、その間 Python に制御が戻らないため SIGINT は確保の完了 / 失敗まで効かない恐れがある（CPU 無限ループでも minijinja は途中で Python シグナルを見ない）。「ハングを Ctrl-C で受けられる」はメモリ爆弾では弱い（未実測）

## Internal Design

### minijinja の露出規則（SSTI 回帰テストで pin）

minijinja がテンプレートに露出するのは、渡した値の **非 `_`・非 dunder のメンバ**（属性・メソッド）と container の items。実測で確定した規則:

- **dunder（`__class__` 等）**: 構造封鎖（undefined）。dot 記法・subscript とも。`attr` / `map(attribute=)` / `selectattr` / `groupby` の string 属性名経由でも同じ
- **`_` 接頭辞の属性・メソッド**: 既定で遮断 — 属性は undefined、メソッド呼び出しはエラー（"insecure method call"）。**dict/list 派生かは無関係、純粋に `_` の有無**。データツリーの内部リンク（`_parent` / `_meta` / `_children()`）をテンプレートから遮断し、marshal されていない素の Python オブジェクト（`_NodeMeta`）へ歩き出せないのはこれによる
- **非 `_` の属性・メソッド**: 露出し、**呼べる**。戻り値もさらに辿れる
- **container items**（dict 値 / list 要素）: map/seq として露出
- **globals**: `_` ブロックは**属性は守るが global 名は守らない** — `_` 名で登録した global も丸見えで、メンバを辿って呼べる。ゆえに engine が global に登録するのはテンプレートヘルパーのみ（filter は独立の名前空間にあり、値として拾えない）
- **loader**: テンプレートが *path* を選ぶ唯一の場所（`include` / `extends` / `import` / `render` filter）だが、`../` も絶対 path も解決しない ＝ template ディレクトリ内に閉じる

さらに marshaling には **convert / wrap の非対称**がある:

- **スカラー（str/int/float/bool/None）は minijinja ネイティブ型へ*変換*（convert）**され、Python のメンバは越境しない。`pycompat=False` なので string に `format` / `format_map` メソッド自体が無い ＝ `str.format` 反射経由の format-string SSTI は不成立
- **オブジェクト（dict/list 派生を含む）は*wrap***され、Python メソッドが漏れる
- ゆえに危険は「wrap される非スカラー（オブジェクト）経由で非 `_` capability に届く」経路に限られる
- `Markup` は convert 側: `__html__` / `unescape` / `striptags` 等の Python メンバは越境しない。一方 `env.finalizer` は Python 値を見るため、エスケープ免除の役目は保たれる

この規則は engine の側にあり、将来版で変わりうる。ゆえに **`test_ssti.py` が古典 SSTI payload を実 render に撃って pin する**。固定するのは両方向 — 封鎖側（上記の sealed 各項）と、設計上の露出側（非 `_` メンバ呼び出し・global 非保護 ＝ marshal 契約が前提とする 2 つのハザード）。露出側が赤になったら侵害ではなく engine の厳格化の合図で、契約を緩められる可能性を意味する。

### marshal 契約 ── テンプレに渡る値を型・構造で inert に閉じる

信頼モデルは「テンプレが触れる値に host capability への経路が無い」ことに懸かる。だが minijinja は渡した値の非 `_`・非 dunder メンバと container items を露出し呼べるようにする（上の露出規則）。しかも**任意 Python オブジェクトの安全性は動的に確認できない** — `__getattr__` / instance 属性 / ABC 登録で内省を欺けるので `dir()` 監査は後手。

ゆえに契約は runtime 検査ではなく、**型と構造でツール側コードの規律を保つ**問題として解く。露出する二系統を各々閉じる:

- **(a) データ**: inert 値モデル `InertValue = str|int|float|bool|None|InertMapping|InertArray` で閉じる。`load_model`（`Any`）由来の木を `ensure_inert` が検証・詰め替え（parse, don't validate）、`MappingNode`/`ArrayNode` が Inert container を継承してアンカーを足す。Inert container は構築後 read-only（mutator は raise。理由は `inert.py`）
- **(b) filters/globals の戻り値**: エンジン所有の受け入れ列挙 `TemplateSafe = InertValue | Node | Markup | MissingNode` で閉じる。

設計の要点:

- **container は派生禁止／スカラーは正規化、の非対称**: container は **wrap** され Python メソッドが漏れるので、派生で capability を足せてはならない。runtime の `ensure_inert` は既に inert な container を `isinstance` でそのまま通す（派生を runtime で弾く検査は無い）ので、派生の封じ込めは静的側 — `MappingNode` / `ArrayNode` の `@final` と、`InertMapping` / `InertArray` を他で継承しないツール側の規律 — が担う。スカラーは **convert** されメンバが届かないので、exact 型へ正規化して受理する
- **`TemplateSafe` は基底でなく列挙**: 受け入れ要件は継承で表せない（派生すれば capability を足せる）ので、各具体型を列挙する:
    - **受け入れ側 `template_safe` が所有し、エンジン境界（`template_engine` と、ヘルパを渡す generator）だけが参照**。生産者は自分の具体戻り型（`Node | MissingNode` 等）を正直に宣言するだけ ── 消費者→生産者の一方向 import ∴ cast も循環も生じない
    - minijinja の undefined は `None` として届き、`pluck` は `None`、`to_yaml` は空文字を返す（`Undefined` 型は列挙に無い）
    - 副作用 callable は原則禁止。`render` filter のみ例外（戻り値 `Markup`。書込 capability は `RenderProcessorImpl` のフィールドで、登録されるのは bound method）

強制のレイヤ（① データ inert / ② foreign 属性不可 / ③④ 非 `_` メソッド・危険 dunder 不可 を担保）:

- **pyright（静的）**: inert container の `[InertValue]` parametrize と、filters/globals 戻り型のエンジン境界照合
- **render 境界ガード（runtime）**: `_bind` が各 binding を `ensure_template_safe` に通し、「テンプレに渡るのは `TemplateSafe` だけ」を入口一点で強制する（engine 所有の非 inert メンバは素通し、data は `ensure_inert` へ、それ以外は raise）。一様性のため内蔵 render も同じ境界を通る。①は加えて `ensure_inert` の詰め替え時のスカラー検証が担保
- **surface-audit テスト**: `TemplateSafe` 各型を MRO 全域で監査する — 非 `_` 表面が参照形（container = 素 dict/list、`MissingNode` = 宣言 field で各値 inert）に一致すること、foreign 属性を植えられないこと（`__slots__`/frozen）、body に想定外 protocol dunder（`__getattr__`/`__getitem__`/`__call__`）が無いこと。`Markup` は convert 側で表面が越境しない（上の露出規則で pin 済み）ため対象外
- **SSTI 回帰テスト（`test_ssti.py`）**: 上の 3 レイヤが前提とする engine 側の露出規則そのものを実 render で pin（前節）
- **残余**: `__slots__` 除去等は behavioral テストが捕まえるが、**監査テスト自体の削除は型でもテストでも防げず code review が担う**
