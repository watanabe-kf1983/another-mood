# Schema

`docs/reference/schema.md` の契約の外で、意図して保つ振る舞い。本文に出るステージ名（`normalize_contents`、`generate`）は[内部構造のステージ表](../20-internal/20-pipeline.md#ステージ構成)のもの。

## `contents/` の読み方

### JSON は、他のプログラムが一度きり出力したものの受け口

手で書くなら YAML、JSON は他のプログラムの出力向け、という勧め（`docs/reference/cli.md` の Which files are read）の背後にある位置づけ。JSON は、LLM の構造化出力・ビルドツール・cron のジョブのように、別のプログラムが一度出力して終わるデータを取り込む入口である。

手で書く人や、対話しながら書くエージェントは、ビルドを回してエラーを直す往復ができる。こうした書き手には、Git の差分が読みやすい YAML が向く。一度出力して終わるプログラムにはその往復がないので、そのプログラムが出せる形式で受ける必要がある。LLM の構造化出力が JSON 向けに作られているのが典型である。

テスト: JSON を受け付けること自体は `tests/components/preprocess/test_content_normalizer.py` の `test_json_source_is_a_record_not_a_blob` が守る。位置づけそのものはテストでは守れない。

### 重複したキーはエラーにする

一つのファイルの中で同じキーが二度現れたら、後の値を採らずエラーにする。YAML でも JSON でも、また contents に限らず schema や views のファイルでも同じだが、理由はデータの側にあるのでここに置く。JSON の仕様（RFC 8259）は重複キーの扱いを実装に任せ、多くの実装は黙って後の値を採るが、黙って値が消えるより止まるほうが安全。`docs/` には書かない。利用者がこれに出会うのはビルドが止まったときで、そのエラーが他の構文エラーと同じく行と列を指すので、文書で予告しなくても何が起きたか分かる。

テスト: `tests/components/shared/user_source/test_source_loader.py` の `test_duplicate_key_rejected_rather_than_last_wins`。

### 一つのコレクションを複数のファイルに分けて書ける

`contents/` のファイルはそれぞれが木の一部で、全ファイルを一つの木に合流させてから後段へ渡す。合流は深い併合で、オブジェクトは再帰的に、配列は連結で合わせる。同じコレクションのレコードを話題ごとのファイルに分けて書けるようにするためで、ファイルの分け方はデータの形に影響しない。

したがって、レコードの id の重複や x-ref（他のレコードへの参照。`docs/reference/schema.md` の Entity references）の解決は、ファイル単位ではなく合流後の木で検査する。

テスト: `tests/components/preprocess/test_content_normalizer.py` の `test_top_level_singleton_split_across_files_is_merged` と `test_ids_duplicated_across_files_fail_validation`。

## レコードの id

### 兄弟の間でだけ一意

同じ配列に並ぶレコード同士が同じ id を持つと、エラーにする。親が違えば、同じ id でも別のレコードであり衝突しない。レコードの住所（アンカーパス。`docs/reference/template.md` の Anchor paths）は親の住所に id をつないで作るので、兄弟の間で一意であれば住所も一意になる。

テスト: `tests/components/preprocess/test_data_id_validator.py` の `TestNestedCollections`。

### map pattern のキーから作る id は常に string

map pattern を配列に直すとき、キーはそのまま `id` になる。YAML のキーには数値・真偽値・日付も書ける（`2024:` は整数として読まれる）が、string でないキーは文字列に変換して id にする。理由:

- ステージ間で受け渡す中間ファイルは JSON で（[JSON データモデル](../20-internal/30-communication/10-json-data-model.md#シリアライズ形式)）、YAML のキーには日付のように JSON で表せない型もある
- [データカタログ](../30-pending/45-schema/10-schema-spec.md#データカタログ)（スキーマから起こした entity と attribute の目録。後段のステージはスキーマの代わりにこれを読む）は id を string と宣言している。実データの型を宣言に合わせる
- x-ref は string 型の attribute にしか付けられない（`docs/reference/schemas/schema-schema.yaml`）。id が string なら、参照の照合は string 同士の比較で済む
- アンカーパスを組み立てる側が、id を常に string と前提できる

`docs/reference/` にはこの変換を書かない。`2024:` のような整数のキーを書く利用者は「2024 という名札」のつもりで書いており、結果がその期待と一致するので、説明が要らない。

テスト: `tests/components/preprocess/test_dict_to_array.py` の `TestFlatDict.test_coerces_int_key_to_string_id`。

## prose

### id に読む順を符号化し、id の安定は捨てる

prose の id は `contents/` からの相対パス（拡張子なし）そのもので、読む順は id の文字列順で決まる。順序を表す別のチャネル（front-matter、目次ファイル）は持たないので、順序はファイル名で表す。ゼロ埋め・隙間空きの番号 prefix（`10-architecture.md`。フォルダの `index` には振らない）はその一つの運用で、dev-docs がそう使っている。

次の三つは同時に満たせない。「読む順がファイルシステム上で見える」には順序をファイル名に入れる必要があり、id がパスそのものなら順序は id にも入る。すると「id が並べ替えに対して安定する」（文書間のリンクは id を住所に使うので、安定しなければ並べ替えでリンクが壊れる）が成り立たない。id を別に宣言すれば両立するが、今度は「id の一意性をファイルシステムが担保する」を失い、重複検査を自前で持つことになる。この判断は二つ目を捨てる。散文の章立ては早く安定し、番号に隙間を空ければ挿入で振り直しは起きない。並べ替えで壊れたリンクは `generate` のリンク解決が報告する。

テスト: `tests/components/preprocess/test_prose.py` の `TestOrderKeySortsToFolderPreorder`（読む順が id だけから決まること）。

### 順序の導出はレコード、ソートはテンプレート

`order_key` と `depth` は id だけから導出できるので、レコードごとに `normalize_contents` が付ける。並べ替えは collection が揃わないとできないので、テンプレート側（`sort(attribute="order_key")`）に置き、並べ替え済みの prose は提供しない。フォルダ木を見出しの入れ子として一冊に綴じる使い方（`dev-docs/definition/reports.yaml` の book edition）は、この二つと `under_heading` フィルタ（`docs/reference/template.md`）だけで書ける。

テスト: `tests/components/preprocess/test_prose.py` の `TestOutlinePosition`。

### 見出しの id は GitHub 互換の slug

見出しの id は見出しテキストから導出する GitHub 互換の slug にする（`## API の設計` → `api-の設計`）。見出しへのリンクが、このツールの Hugo 出力・GitHub・VS Code のプレビューのどれで見ても同じ場所に着地するためで、規則の正本は `github_slug` の docstring。`{#id}` のような明示記法は採らない。テキスト由来なら id と見出しが乖離しないため。id の安定は「変わらないこと」ではなく「壊れた参照はビルドが報告すること」で担保する。

テスト: `tests/components/shared/test_markdown.py` の `TestGithubSlug`。

### 相対リンクは `node:` 化し、同一ページ内の `#fragment` は変換しない

本文中の、`contents/` 内に解決する相対リンクはすべて `node:` 記法（レコードの住所で宛先を指す書き方。`docs/reference/template.md` の Anchor paths）に書き換える。edition ごとに分割粒度が変わると（`docs/reference/reports.md`）リンク先のページも変わるので、生の相対パスを残すと別の分割の出力で壊れる。`node:` 化して `generate` の解決に委ねれば、出力構造が変わってもリンクが追従する。`#fragment` も同じ理由で `node:` URI に乗せて運ぶ。

一方、純粋な `#fragment` は変換しない。prose は必ず一つのファイル全体が一ページに描かれるので、同一文書内の参照は常に同じページ内に着地し、壊れない。

書き換えはレキシカルで、リンク先が存在するかはここでは見ない。存在の検証は `generate` のリンク解決に委ねる（[内部構造](../20-internal/10-architecture.md#ステージをまたぐ約束)）。

テスト: `tests/components/preprocess/test_prose.py` の `TestNormalizeLinksConverted` と `TestNormalizeLinksVerbatim`。

## blob

### id は拡張子込み

blob の id は `contents/` からの相対パスで、拡張子を含む。落とすと `fig.png` と `fig.jpg` が衝突する。prose の拡張子なし id は `.md` が唯一の拡張子だから成立する省略で、blob には適用しない。

テスト: `tests/components/shared/user_source/test_source_loader.py` の `test_record_shape_keeps_extension_and_no_bytes`。

### バイト列はレコードに載せない

blob のレコードは id と mime_type だけで、中身のバイト列を持たない。base64 で載せるとレコードが肥大し、メモリと Git の差分を壊す。id から実ファイルの位置が復元できるので、バイト列を出力まで運ぶ側（[運搬機構](../20-internal/30-communication/index.md#運搬機構)）はそこから読む。

テスト: `tests/components/shared/user_source/test_source_loader.py` の `test_record_shape_keeps_extension_and_no_bytes`。
