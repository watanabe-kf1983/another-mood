# 奥付 (appendix)

[奥付](../../../20-design/75-meta-documentation/20-build-information.md) の背景。

## データ層には流さない

build info をシステム定義エンティティ（`__build_info`）として preprocess から流す案は、機構としては成立する（`__definition` が先例で、views から join でき、`__data` 診断にも tap にも自動で乗る）。それでも採らない理由は 2 つ。

**views の出力が実行環境で変わるようになり、これは一方通行**。views が読めるようにした後で取り上げると利用者の views が壊れる。逆向き（奥付方式から後で data 層へ移す）なら余地が残る。もう一つは **ビルド失敗ページに届かない**こと。preprocess で吐く以上、上流で失敗すれば reconcile からは見えず、奥付を出す 2 か所（表紙・失敗ページ）の片方が原理的に成立しない。

同じ理由で tap にも provenance を載せない。tap 出力は差分を取る使い方が主なので、毎回動く値が混ざると実質的な差分がノイズに埋もれる。守る線は「ソースだけで決まる」ではなく **「マシンと起動のしかたには依存しない」**（tap 出力には既に `__definition` 等のツール生成目録が乗っており、ツール版には依存している）。

## キーの出所の取り方

本文の Internal Design（上流で組んで運ばない）と同じ理由で `manifest.*` も、`Manifest` の型付きフィールドをそのまま射影する（`ProjectConfig` には pydantic の `model_dump`、`Manifest` には `dataclasses.asdict`）。欄を足したときに射影側の登録漏れで奥付から静かに落ちることがなく、manifest スキーマがトップレベルを `additionalProperties: false` で閉じている以上、フィールドの集合は定義上ちょうど網羅的になる。生の mapping を別に抱える形は採らない — 型に落とせないのは `tools` だけで、他処理系の名前空間 `tools.<processor>` の中身はスキーマが無制約にしている部分なので `Mapping[str, object]` が正しい型。入れ子はストアの平坦化が dotted に潰す。

`processor.config.*` は config の写しで、実効値は混ぜない。ずれるのは作業ディレクトリだけ — `tmp_dir` 未固定なら config には無いが、使い捨てのディレクトリは実在する。これを `processor.workspace.*`（`root` / `temporary`）として分ける。内部エラーの run はこのディレクトリを post-mortem 用に残すので（`command._discard_workspace`）、奥付を埋め込むビルド失敗ページでは残存パスとして読める。`temporary` が要るのは、`root` が「消えた使い捨て」か「利用者が固定したディレクトリ」かで読み方が変わるため。
