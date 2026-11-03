# テンプレート評価の境界

外部設計の [Trust Model](../10-external/70-trust-model.md) が約束する「テンプレートから任意コードは走らない」を、どう閉じているか。

複数のモジュールと二つのテストが分担して守る約束なので、分担の全体はここに置き、各モジュールは自分の分担だけをコメントに持つ:

- `generator/template_engine.py` — 評価器と、描画の入口の境界ガード
- `generator/inert.py` — データの inert 値モデル
- `generator/template_safe.py` — ヘルパの戻り値の受け入れ列挙
- `generator/data_tree.py` — ノードと、`_` 接頭辞のメタデータ
- `generator/render_processor.py` — 唯一の副作用フィルタ `render`
- `tests/components/generator/test_ssti.py` / `test_template_safe.py` — エンジンの露出規則と、型の表面の監査

本文で使う語:

- **host の capability** — テンプレートの外にある、ファイル・プロセス・ネットワーク等に届く Python の機能
- **SSTI** — テンプレートに仕込んだ式で host の capability に届こうとする攻撃（server-side template injection）
- **inert な値** — host の capability への経路を持たない値。テンプレートに見せてよい値
- **marshal** — Python の値をテンプレートの値モデルへ渡す変換。スカラーは変換（convert）され、オブジェクトは包まれる（wrap）
- **finalize / `Markup` / 主題** — 外部設計の [Template](../10-external/50-template.md) の語
- **ノード** — 住所（アンカーパス）を持つ container。`MappingNode` / `ArrayNode` の二種で、型としては `Node`。外部設計の Template が言うノード（リンクの宛先）より狭く、prose の見出しは含まない。壊れた参照の値は `MissingNode`（外部設計の [Template](../10-external/50-template.md)）

## 評価器は一つ

Jinja の評価器は `TemplateEngine`（`generator/template_engine.py`）だけで、持つのは generator コンポーネント（`generate` と `reconcile` のステージ）に限る。

`generate` は著者のテンプレートに加え、内蔵テンプレート（表紙、`__db/` のメタドキュメント）を描く。`reconcile` が描くのは内蔵テンプレート（失敗ページ・奥付・警告）だけで、渡す値も `BuildReport` と build info だけ。`site` は Markdown を変換するだけで、著者のテンプレートもデータ木も見ない。

外部設計が依存するのは「テンプレートに渡る値がすべて同じ境界を通る」こと。評価器を一つに保つのはその最も単純な保ち方で、増やさない。

## 値モデルで閉じ、ブロックリストでは閉じない

Jinja2 の SSTI 経路（`__class__` から `__subclasses__()` へ、`attr('__class__')`、`map(attribute=)` 等）は独立した穴の集まりではなく、「Python オブジェクトをリフレクションで触る」値モデル一つから生えている。

だから Jinja2 の `SandboxedEnvironment` のように危険属性を都度禁じる実行時サンドボックスは採らない。`attr` / `map(attribute=)` のような属性名で辿るフィルタはテンプレートで広く使われ、禁じられない。

採ったのは、値モデルが構造的に安全なエンジン（minijinja。値を Rust 側で持ち、Python のリフレクションの入口である dunder が無い）と、その上に置く [marshal 契約](#marshal-契約-テンプレートに渡る値を型と構造で-inert-に閉じる)。エンジンだけでは足りない。渡した Python オブジェクトの通常のメンバは露出するので、渡す値の側を契約で閉じる。

## DoS は閉じない

外部設計の [Trust Model](../10-external/70-trust-model.md#dos-は閉じず実行者が-os-層で囲う) が「時間やメモリの上限はツールが持たない」と定める背後の分析:

- **単発の爆弾は minijinja が構造で拒む**。`range(n)` の要素数上限、テンプレートの再帰上限、文字列・シーケンスの `*` 反復上限があり、`"x" * 10**12` 型の一撃は通らない
- **残るのは累積と増幅**で、命令数ではなくバイト数で膨れる。倍々の連結（`ns.x ~ ns.x` を N 回で 2^N バイト）、フィルタの増幅（`| indent(巨大幅)` は小さな入力をスカラー引数で巨大な出力にする）、データ列のネストループ。各段は合法なサイズで、総量だけが爆発する
- **minijinja の `fuel` では閉じない**。`fuel` は命令一個を 1 とする CPU の予算で、確保したバイト数を見ないため、上のメモリ増幅は命令数が小さく素通りする。既定で ON にすると、メモリを止めないのに上限があるように見え、誤った安心を配る
- **時間もツール側では止められない**。評価はネイティブ拡張の中で走り、巨大な確保や長いループの間は Python に制御が戻らない。ツール側のタイムアウトもシグナルも、評価の途中には届かない
- **OS 層の制限なら閉じる**。`RLIMIT_AS` は確保要求そのものを失敗させるので、スラッシュや無作為な OOM-kill ではなく当該プロセスを決定的に落とす。cgroup やコンテナは時間も CPU も同じ場所で縛る

`fuel` を足したくなる場所は `make_environment`（`generator/template_engine.py`）。

## 前提: minijinja が露出するもの

minijinja がテンプレートに露出するのは、渡した値の非 `_`・非 dunder のメンバ（属性・メソッド）と container の要素。実測で確定した規則:

- **dunder**（`__class__` 等）は構造封鎖。dot 記法、subscript、`attr` / `map(attribute=)` / `selectattr` / `groupby` の文字列属性名のどれからも届かない
- **`_` 接頭辞**の属性は undefined、メソッド呼び出しはエラー。dict / list 派生かは無関係で、純粋に `_` の有無。データ木の `_parent` / `_meta` をテンプレートから遮断し、素の Python オブジェクトへ歩き出せないのはこれによる
- **非 `_` の属性・メソッド**は露出し、呼べる。戻り値もさらに辿れる
- **globals** は `_` 名でも守られず、メンバを辿って呼べる。だからエンジンが global に登録するのはテンプレートヘルパだけ（filter は別の名前空間にあり、値として拾えない）
- **loader** はテンプレートがパスを選ぶ唯一の場所（`include` / `extends` / `import` / `render`）だが、`../` も絶対パスも解決せず、テンプレートディレクトリに閉じる

marshal には convert と wrap の非対称がある。スカラー（str / int / float / bool / None とその派生）は minijinja ネイティブの値に変換され、Python のメンバは越境しない。

`pycompat`（Python のメソッドを値に生やす minijinja のオプション。外部設計の [Template](../10-external/50-template.md)）も切っているので、文字列に `format` / `format_map` が無く、`str.format` の反射経由の SSTI も不成立。

一方オブジェクト（dict / list 派生を含む）は wrap され、Python のメソッドが漏れる。だから危険は「wrap される非スカラー経由で非 `_` の capability に届く」経路に限られる。

`Markup` は str の派生なので convert 側で、テンプレートからは素の文字列に見え、`__html__` / `unescape` 等の Python メンバには届かない。

それでも finalize には `Markup` のまま届く。エンジンの Python binding が finalize に元の Python オブジェクトを渡すためで、escape 免除の役目は保たれる（`test_ssti.py` の `TestMarkupExposure` が pin）。

この規則はエンジンの側にあり、将来版で変わりうる。だから `tests/components/generator/test_ssti.py` が古典的な SSTI payload を実 render に撃って pin する。

固定するのは両方向で、封鎖側（上の各項）と、設計が前提とする露出側（非 `_` メンバの呼び出し、global の非保護）。露出側が赤になったら侵害ではなくエンジンの厳格化の合図で、契約を緩められる可能性を意味する。

## marshal 契約: テンプレートに渡る値を型と構造で inert に閉じる

任意の Python オブジェクトの安全性は動的に確認できない。`__getattr__`、インスタンス属性、ABC 登録で内省を欺けるので、`dir()` による監査は後手になる。

だから契約は実行時の検査ではなく、型と構造でツール側のコードの規律を保つ問題として解く。露出する二系統を各々閉じる:

- **データ**: inert 値モデル `InertValue = str | int | float | bool | None | InertMapping | InertArray`（`generator/inert.py`）
- 前段の出力から読んだ木（型は `object`）を `ensure_inert` が検証して詰め替え（parse, don't validate）、`MappingNode` / `ArrayNode` が inert container を継承して住所を足す
- inert container は構築後 read-only で、mutator は raise する。データ木は全ページの描画で共有され、非 `_` のメソッドはテンプレートから呼べるため
- **ヘルパ（filter / global）の戻り値**: エンジンが所有する受け入れの列挙 `TemplateSafe = InertValue | Node | Markup | MissingNode`（`generator/template_safe.py`）

設計の要点:

- **container は派生を封じ、スカラーは正規化する、の非対称**。container は wrap されて Python のメソッドが漏れるので、派生で capability を足せてはならない。派生してよいのは住所を足す `MappingNode` / `ArrayNode` だけ
- データのスカラーは convert されてメンバが届かないので、派生を弾く必要が無い。代わりに exact な型に正規化して、静的型 `InertValue` が前提にする exact な型に実体を揃える。`Markup` はデータではなくヘルパの戻り値で、`TemplateSafe` として別に受理する
- 派生の封じ込めは静的側が担う。`ensure_inert` は既に inert な container を `isinstance` でそのまま通し、派生を実行時に弾く検査は無い。`MappingNode` / `ArrayNode` の `@final` と、inert container を他で継承しない規律で保つ
- **`TemplateSafe` は基底型でなく列挙**。受け入れ要件は継承で表せない（派生すれば capability を足せる）ので、各具体型を列挙する
- `TemplateSafe` は受け入れ側が所有し、エンジン境界（`template_engine` と、ヘルパを渡す generator）だけが参照する。生産者は自分の具体的な戻り型（`Node | MissingNode` 等）を宣言するだけで、消費者から生産者への一方向 import になる
- minijinja の undefined は `None` として届き、ヘルパは `None` を返す（`Undefined` 型は列挙に無い）
- **副作用のある callable は原則禁止**。`render` フィルタだけが例外で、ページを書き出す。テンプレートが選べるのはサブテンプレートの名前と主題だけで、書き込み先はツールが主題の住所から決め、出力ディレクトリに閉じる。フィルタは値として拾えない（前提）ので、持ち主のオブジェクトへ辿る経路も無い

## 強制のレイヤ

契約が担保する要件は三つ:

- ① テンプレートに渡るデータは inert である
- ② `TemplateSafe` の型に宣言外の属性（foreign な属性）を植えられない。植えられると、非 `_` の属性として露出し、capability を運びうる
- ③ `TemplateSafe` の型は、基準の表面（素の dict / list、宣言した field）を超える非 `_` のメソッドも、protocol dunder も持たない。`__getattr__` / `__getitem__` / `__call__` は、テンプレートが名前で辿れなくても、エンジンや Python が protocol として自分で呼ぶので発動する

層ごとに担う要件を添える:

- **pyright（静的）** — ①と②。inert container の `[InertValue]` による型付けと、ヘルパの戻り型のエンジン境界での照合
- **render 境界ガード（実行時）** — ①。描画の入口（`template_engine.py` の `_bind`）は主題を `this` に束縛し、主題が map ならその各キーも束縛する。その各 binding を `ensure_template_safe` に通し、「テンプレートに渡るのは `TemplateSafe` だけ」を一点で強制する
- 境界ガードは `Markup` と `MissingNode` を素通しし、データは `ensure_inert` へ回し、それ以外は raise する。一様性のため、内蔵テンプレート（表紙、メタドキュメント、失敗ページ、奥付、警告）の描画も同じ境界を通る
- **surface-audit テスト**（`tests/components/generator/test_template_safe.py`） — ②と③。`TemplateSafe` の各型を MRO 全域で監査する。非 `_` の表面が基準の表面（container は素の dict / list、`MissingNode` は宣言した field で各値が inert）に一致すること
- 同じテストで、foreign な属性を植えられず（`__slots__` / frozen）、想定外の protocol dunder が無いことも見る。`Markup` は convert 側で表面が越境しないので対象外（SSTI 回帰テストが pin）
- **SSTI 回帰テスト**（`test_ssti.py`） — 上の三層が前提とするエンジン側の露出規則そのものを実 render で pin する（[前提](#前提-minijinja-が露出するもの)）
- **残余** — `__slots__` の除去などは behavioral なテストが捕まえるが、監査テスト自体の削除は型でもテストでも防げず、code review が担う
