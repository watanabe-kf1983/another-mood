# 奥付

ビルドそのものの記録（処理系・注入値・manifest）を可視化する機能。出力は `__build_info/` に置く。

## External Design

### 奥付

> **[W4 dup]** ↔ generator.py:115-118 (ファイル境界)、workspace.py:69-81 (config 全量、workspace.*)、build_info.py:16-18,40-42 (行が無い/書式)、generator.py:84-87 (失敗ページ)、command.py:294-304 (a)、template.md:358-360 (b) — 部分〜完全。案?: 設計判断は design→残し、コード側コメント (workspace.py、build_info.py、generator.py) を一文に縮める

奥付はストアの全量を列挙する独立ページ (`__build_info/`) で、表紙 (`index.md`) からはリンク節 (`## Build Information`) だけが張られる。`__warnings/` `__db/` と同じ形で、表紙の節見出しは `Database Information` に倣った綴り（パスの綴りは関数名 `build_info` 側に揃える）。

**ファイル境界を分けるのは、利用者が公開対象から外せるようにするため。** 奥付が語るのはビルドした環境の事実（実行者が注入した値、sbdb プロジェクトの絶対パス等）で、出力を公開する利用者にとっては読者が「ビルドした人」ではなくなる。表紙に混ぜ込むと外す手段が無いが、ディレクトリが分かれていれば `__build_info/` 一つを除外指定するだけで済む。ビルド結果をコミットする利用者にとっても、毎回動くタイムスタンプで表紙が汚れなくなる（動かないタイムスタンプに意味はないので、差分が出ること自体は仕様）。

**除外機構はツールに持たせない。** 何を公開するかはデプロイ手段（rsync / `aws s3 sync` / CI）の仕事で、ツールが公開ポリシーのフラグを持ち始めると同種の要求が積み上がる。ツールが負うのは「一箇所にまとまっていること」だけ。`__warnings/` も同じ立場。

**表紙のリンク節に値は載せない。** 要約を載せると「どのキーが表紙に値するか」という裁定が復活し、下の非契約宣言と衝突する。

**config は選ばず全量載せる**（`processor.config.*`。`vars` だけは `vars.*` 側に出す）。奥付が答えるのは「この run はどう起動されたか」で、config はその問いそのもの。部分集合にすると「どれが有用か」というツール側の趣味判断になる。`host` / `port` のように build では効かないパラメータも並ぶが、run の種別は `processor.command` として同じページにある。

**行が無いことは「その run でそれが起きなかった」を意味する**（watch に `site_dir` が無いのは publish しないから）。空欄の行を置くと `build_info(key, default)` の `default` が効かなくなる。この読み方を守るため、config が語らない実効値は別のキーで出す（作業ディレクトリ → `processor.workspace.*`）。値の書式はツールが発明しない（時刻は ISO 8601 一本、bool は YAML 綴り）。

パスは絶対で載せる。`namespace_root` 相対の tail は MCP で `.` に潰れ、チャネルによって情報量が変わる識別子になる。ローカルパスが公開物に出ることは、上のファイル境界で受け止める。

**ビルド失敗ページだけは奥付を埋め込む。** 失敗ページを読むのは必ずビルドした人であり、失敗した出力を公開する利用者は居ない。診断が既に絶対パスを焼いているページでもある。

### build_info のキーの名前空間 — 出所で三分する

> **[W4 dup]** vars の綴り規則 ↔ template.md:358、cli.md:268-274 (b)、25-entrypoints/10-config-spec:27-29 (c)、50-release:51-53 (c) — 部分。案: 綴り規則は削除→docs (config-spec へポインタ)。非契約宣言は残す

| 名前空間 | 出所 | 例 |
|---|---|---|
| `processor.*` | 今回処理した処理系 | `processor.name`, `processor.version`, `processor.started_at`, `processor.command` |
| `vars.*` | 実行者の注入値（供給機構は [20-config-spec.md](../25-entrypoints/10-config-spec.md)） | `vars.git_commit_id` |
| `manifest.*` | sbdb プロジェクトの宣言 (sbdb.yaml) | `manifest.title`, `manifest.sbdb_version` |

注入ルートは `vars.*` にしか書けない。処理系の識別（`processor.name` / `version` / `started_at` / `command`）と `manifest.*` を外から偽装する経路は無い（`processor.config.*` は環境変数 `MOOD_*` でも決まるが、それは config の写しであって注入ではない）。環境変数の素通し（`env.*`）を作らないのも同じ線で、テンプレートが環境の読み取り器になると CI のクレデンシャル等を出力に焼き込めてしまう（[25-template-trust-model.md](../70-generator/25-template-trust-model.md) の閉じた値モデルに穴を開ける）。越境するのは実行者が明示的に差し出した値だけ。

`processor.*` / `manifest.*` のキー目録は `docs/` で**意図的に非契約**とし、「処理系が供給するもので、目録はバージョン間で変わりうる。奥付ページで確認せよ」と明言する（沈黙を暗黙の安定保証に読ませない）。release.md の feature / breaking 判定は「docs/reference の約束の集合」に基づくため、目録を約束しないことでキーの増減・改廃がリリース分類上の破壊にならない。

**`vars.*` はその例外**で、キーを決めるのは利用者。ツールが約束するのは綴りの対応規則（環境変数は封筒を剥がして小文字化、`--var` / MCP は書いたまま）と、**注入した値は全て奥付ページに出る**こと。一つのテンプレートで使うつもりで注入した値も載るので、docs に明記している。

### 背景: データ層には流さない

> **[W4 → appendix]**

build info をシステム定義エンティティ（`__build_info`）として preprocess から流す案は、機構としては成立する（`__definition` が先例で、views から join でき、`__data` 診断にも tap にも自動で乗る）。それでも採らない理由は 2 つ。

**views の出力が実行環境で変わるようになり、これは一方通行**。views が読めるようにした後で取り上げると利用者の views が壊れる。逆向き（奥付方式から後で data 層へ移す）なら余地が残る。もう一つは **ビルド失敗ページに届かない**こと。preprocess で吐く以上、上流で失敗すれば reconcile からは見えず、奥付を出す 2 か所（表紙・失敗ページ）の片方が原理的に成立しない。

同じ理由で tap にも provenance を載せない。tap 出力は差分を取る使い方が主なので、毎回動く値が混ざると実質的な差分がノイズに埋もれる。守る線は「ソースだけで決まる」ではなく **「マシンと起動のしかたには依存しない」**（tap 出力には既に `__definition` 等のツール生成目録が乗っており、ツール版には依存している）。

## Internal Design

### build_info のキーを足す場所 — `Workspace` の `build_info` property

> **[W4 dup]** ↔ workspace.py:60-85 (a, 部分〜完全)。機構。案: 削除→コード (design にしかない理由はコメントへ)

キーは `Workspace` が既に型付きで持っている値の平坦化なので、上流で組んで運ぶ形にはしない（同じ事実が二重に載る）。ただし `pipeline/` はカバレッジ計測対象外なので、平坦化そのものは `components/shared/` の汎用ヘルパに置く。property が持つのは「どのキーがどの源から来るか」だけ。

同じ理由で `manifest.*` も、`Manifest` の型付きフィールドをそのまま射影する（`ProjectConfig` には pydantic の `model_dump`、`Manifest` には `dataclasses.asdict`）。欄を足したときに射影側の登録漏れで奥付から静かに落ちることがなく、manifest スキーマがトップレベルを `additionalProperties: false` で閉じている以上、フィールドの集合は定義上ちょうど網羅的になる。生の mapping を別に抱える形は採らない — 型に落とせないのは `tools` だけで、他処理系の名前空間 `tools.<processor>` の中身はスキーマが無制約にしている部分なので `Mapping[str, object]` が正しい型。入れ子はストアの平坦化が dotted に潰す。

`processor.config.*` は config の写しで、実効値は混ぜない。ずれるのは作業ディレクトリだけ — `tmp_dir` 未固定なら config には無いが、使い捨てのディレクトリは実在する。これを `processor.workspace.*`（`root` / `temporary`）として分ける。内部エラーの run はこのディレクトリを post-mortem 用に残すので（`command._discard_workspace`）、奥付を埋め込むビルド失敗ページでは残存パスとして読める。`temporary` が要るのは、`root` が「消えた使い捨て」か「利用者が固定したディレクトリ」かで読み方が変わるため。
