# 奥付

ビルドそのものの記録（処理系・注入値・manifest）を可視化する機能。出力は `__build_info/` に置く。

## External Design

### 奥付

奥付はストアの全量を列挙する独立ページ (`__build_info/`) で、表紙 (`index.md`) からはリンク節 (`## Build Information`) だけが張られる。`__warnings/` `__db/` と同じ形で、表紙の節見出しは `Database Information` に倣った綴り（パスの綴りは関数名 `build_info` 側に揃える）。

**ファイル境界を分けるのは、利用者が公開対象から外せるようにするため。** 奥付が語るのはビルドした環境の事実（実行者が注入した値、sbdb プロジェクトの絶対パス等）で、出力を公開する利用者にとっては読者が「ビルドした人」ではなくなる。表紙に混ぜ込むと外す手段が無いが、ディレクトリが分かれていれば `__build_info/` 一つを除外指定するだけで済む。ビルド結果をコミットする利用者にとっても、毎回動くタイムスタンプで表紙が汚れなくなる（動かないタイムスタンプに意味はないので、差分が出ること自体は仕様）。

**除外機構はツールに持たせない。** 何を公開するかはデプロイ手段（rsync / `aws s3 sync` / CI）の仕事で、ツールが公開ポリシーのフラグを持ち始めると同種の要求が積み上がる。ツールが負うのは「一箇所にまとまっていること」だけ。`__warnings/` も同じ立場。

**表紙のリンク節に値は載せない。** 要約を載せると「どのキーが表紙に値するか」という裁定が復活し、下の非契約宣言と衝突する。

**config は選ばず全量載せる**（`processor.config.*`。`vars` だけは `vars.*` 側に出す）。奥付が答えるのは「この run はどう起動されたか」で、config はその問いそのもの。部分集合にすると「どれが有用か」というツール側の趣味判断になる。`host` / `port` のように build では効かないパラメータも並ぶが、run の種別は `processor.command` として同じページにある。

**行が無いことは「その run でそれが起きなかった」を意味する**（watch に `site_dir` が無いのは publish しないから）。空欄の行を置くと `build_info(key, default)` の `default` が効かなくなる。この読み方を守るため、config が語らない実効値は別のキーで出す（作業ディレクトリ → `processor.workspace.*`）。値の書式はツールが発明しない（時刻は ISO 8601 一本、bool は YAML 綴り）。

パスは絶対で載せる。`namespace_root` 相対の tail は MCP で `.` に潰れ、チャネルによって情報量が変わる識別子になる。ローカルパスが公開物に出ることは、上のファイル境界で受け止める。

**ビルド失敗ページだけは奥付を埋め込む。** 失敗ページを読むのは必ずビルドした人であり、失敗した出力を公開する利用者は居ない。診断が既に絶対パスを焼いているページでもある。

### build_info のキーの名前空間 — 出所で三分する

| 名前空間 | 出所 | 例 |
|---|---|---|
| `processor.*` | 今回処理した処理系 | `processor.name`, `processor.version`, `processor.started_at`, `processor.command` |
| `vars.*` | 実行者の注入値（供給機構は [20-config-spec.md](../25-entrypoints/10-config-spec.md)） | `vars.git_commit_id` |
| `manifest.*` | sbdb プロジェクトの宣言 (sbdb.yaml) | `manifest.title`, `manifest.sbdb_version` |

注入ルートは `vars.*` にしか書けない。処理系の識別（`processor.name` / `version` / `started_at` / `command`）と `manifest.*` を外から偽装する経路は無い（`processor.config.*` は環境変数 `MOOD_*` でも決まるが、それは config の写しであって注入ではない）。環境変数の素通し（`env.*`）を作らないのも同じ線で、テンプレートが環境の読み取り器になると CI のクレデンシャル等を出力に焼き込めてしまう（[25-template-trust-model.md](../70-generator/25-template-trust-model.md) の閉じた値モデルに穴を開ける）。越境するのは実行者が明示的に差し出した値だけ。

`processor.*` / `manifest.*` のキー目録は `docs/` で**意図的に非契約**とし、「処理系が供給するもので、目録はバージョン間で変わりうる。奥付ページで確認せよ」と明言する（沈黙を暗黙の安定保証に読ませない）。release.md の feature / breaking 判定は「docs/reference の約束の集合」に基づくため、目録を約束しないことでキーの増減・改廃がリリース分類上の破壊にならない。

**`vars.*` はその例外**で、キーを決めるのは利用者。ツールが約束するのは綴りの対応規則（`docs/reference/cli.md` の Injected values 節が正本）と、**注入した値は全て奥付ページに出る**こと。一つのテンプレートで使うつもりで注入した値も載るので、docs に明記している。

### データ層には流さない

build info はシステム定義エンティティとして preprocess から流さず、tap にも provenance を載せない。理由は[背景](../../90-appendix/20-design/75-meta-documentation/20-build-information.md#データ層には流さない)。

## Internal Design

### build_info のキーを足す場所 — `Workspace` の `build_info` property

キーは `Workspace` が既に型付きで持っている値の平坦化なので、上流で組んで運ぶ形にはしない（同じ事実が二重に載る）。ただし `pipeline/` はカバレッジ計測対象外なので、平坦化そのものは `components/shared/` の汎用ヘルパに置く。property が持つのは「どのキーがどの源から来るか」だけ。

`manifest.*` を型付きフィールドの射影で出す理由と、`processor.workspace.*` を config と分ける理由は[背景](../../90-appendix/20-design/75-meta-documentation/20-build-information.md#キーの出所の取り方)。
