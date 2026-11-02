# Normalizer

`contents/` 配下のソースファイルを読み、一つのデータ木に仕上げるステージ（パイプラインの `normalize_contents`）。`components/preprocess/content_normalizer.py` が次の順に処理する:

1. 各ファイルを拡張子で振り分けて読む。YAML と JSON は構造化データ、Markdown は [prose](25-prose-spec.md)、それ以外は [blob](27-blob-spec.md) になる
2. 利用者のスキーマに内蔵スキーマ（prose / blob）を合わせたもので、ファイルごとに検証する
3. map pattern（キーを名札にしてレコードを並べる書き方。`docs/reference/schema.md` の Map pattern 節）を、`[{id: <キー>, ...}]` の配列に直す（`normalize_core.py`）
4. 全ファイルの結果を一つの木に合流させる
5. 合流した木で、x-ref（他のレコードへの参照）が解決できるかを検査し（できなければ警告）、レコードの id の重複を検査する（重複はエラー）

どのファイルを読むか（拡張子の振り分け、dotfile の除外）は `docs/reference/cli.md` の Which files are read 節が約束しており、ここでは繰り返さない。

## External Design

### JSON は、他のプログラムが一度きり出力したものの受け口

YAML と JSON はどちらも構造化データとして受け付けるが、想定する書き手が違う。手で書くなら YAML を勧める（`docs/reference/cli.md`）。JSON は、LLM の構造化出力・ビルドツール・cron のジョブのように、別のプログラムが一度出力して終わるデータを取り込む入口と位置づける。

手で書く人や、対話しながら書くエージェントは、ビルドを回してエラーを直す往復ができる。こうした書き手には、Git の差分が読みやすい YAML が向く。一度出力して終わるプログラムにはその往復がないので、そのプログラムが出せる形式で受ける必要がある。LLM の構造化出力が JSON 向けに作られているのが典型である。

### レコードの id は兄弟の間でだけ一意

同じ配列に並ぶレコード同士が同じ id を持つと、エラーにする。親が違えば、同じ id でも別のレコードであり衝突しない。レコードの住所（[アンカーパス](../70-generator/30-anchor-spec.md)）は親の住所に id をつないで作るので、兄弟の間で一意であれば住所も一意になる。

検査は全ファイルを合流させた後に一度だけ行う（`data_id_validator.py`）。一つの配列のレコードを複数のファイルに分けて書けるので、ファイル単位では重複を見つけられない。

### map pattern のキーから作る id は常に string

map pattern を配列に直すとき、キーはそのまま `id` になる。YAML のキーには数値・真偽値・日付も書ける（`2024:` は整数として読まれる）が、string でないキーは文字列に変換して id にする。理由:

- ステージ間で受け渡す中間ファイルは JSON で、YAML のキーには日付のように JSON で表せない型もある
- [データカタログ](../45-schema/10-schema-spec.md#データカタログ)（スキーマから起こした entity と attribute の目録。後段のステージはスキーマの代わりにこれを読む）は id を string と宣言している。実データの型を宣言に合わせる
- x-ref は string 型の attribute にしか付けられない（`docs/reference/schemas/schema-schema.yaml`）。id が string なら、参照の照合は string 同士の比較で済む
- アンカーパスを組み立てる側が、id を常に string と前提できる

利用者向けの `docs/reference/` にはこの変換を書かない。`2024:` のような整数のキーを書く利用者は「2024 という名札」のつもりで書いており、結果がその期待と一致するので、説明が要らない。

## Internal Design

### `.json` も YAML のリーダで読む

利用者が書く YAML / JSON ファイル（スキーマ、contents、views、reports、マニフェスト）は、すべて `shared/user_source/source_loader.py` の `parse_mapping` で読む。`.json` もここを通る。YAML 1.2 は JSON を包含するので、同じリーダで読める。

この読み込み経路は、キーと文字列値に元ファイル上の位置を持たせる（`UserStr`）。エラーや警告はこの位置を使って、利用者が書いた行と列を指す。後段の検査の一部（views の名前の検査など）は、位置を持たない値を内部バグとして扱う。JSON 専用のパーサを足すと、位置を持たせる仕組みをもう一つ作ることになるので、足さない。

この選択によって、`.json` の中に YAML の書き方が混ざっても読めるが、このままにする。`docs/` はこれを約束しておらず、弾くには JSON 専用のパーサを前に置く必要があり、上の判断と衝突する。
