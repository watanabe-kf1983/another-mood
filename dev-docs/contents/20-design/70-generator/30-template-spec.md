# Template Specification

## External Design

### 背景: なぜ Undefined をエラーにしないか

Jinja2 は `undefined` クラスを差し替え可能で、厳密な `StrictUndefined`（全ての undefined アクセスでエラー）、チェイン可能な `ChainableUndefined`、デフォルトの `Undefined`（1 階層目はサイレント、チェインはエラー）の 3 段階を提供する。

本プロジェクトは `ChainableUndefined` を採用する。理由:

- 内蔵テンプレート・ユーザテンプレートのいずれも、スキーマから抽出される optional フィールド（`metadata`, `validation` 等）を頻繁に参照するため、ガードの記述負荷が重い
- デフォルトの `Undefined` は 1 階層目の typo も同様にサイレント失敗するため、チェインだけエラーにする中途半端な挙動になっている
- 厳密な typo 検出が必要になった時点で `StrictUndefined` への切り替えを検討する（その際は内蔵テンプレート側のガード追加が必要）

## Proposals

### render の filter 化

`{% render "tpl" with subject %}`（仕様は [paging-spec のテンプレート主題](40-paging-spec)）を **filter 形 `{{ subject | render("tpl") }}` でも呼べるようにする**。まずタグと併存させ（P7）、稼働プロジェクトが filter へ移り切ったらタグを撤去する（P8）── P4 / P5（`mood_view` エイリアスの併存追加 → 廃止）と同じ二段構え。

背景: タグにした本来の目的は *page 生成を文位置に置く statement 構文*（`{% section %}` として導入、`with` 構文は化粧）で、`{% render %}` の行を指すエラーは subtree guard 導入時に **parse 位置を後から相乗り**させた副次にすぎない（本来目的ではない）。ゆえに filter 化で失うのは化粧＋行精度のみで、後者はエンジン移行後どのみち縮む（minijinja filter は `state.name` まで、liquid filter も行は落ちる）。

利点:

- **唯一の Jinja 拡張 `RenderExtension` が消え**、素の `Environment` だけになる。render が `node` / `link` と同じ curated helper 語彙（パイプ）に揃う。
- エンジン移行（[P6](60-template-trust-model)）の障害を消す: **minijinja はカスタムタグ非対応**なので、タグ廃止（P8）まで済めば移行がタグに阻まれない。filter 追加（P7）は engine 中立で **現 Jinja2 でも実施可**。
- globals 衛生（[trust-model の marshal 契約](60-template-trust-model)）に効く: processor が filter closure に captured され、`env.globals[PROCESSOR_KEY]` の operational オブジェクト露出が消える。
- 合成が素直: `{{ member | render("member.md") | under_heading("##") }}`（現状は `{% filter %}` ブロック3行）。

決定:

- **filter 形（`subject | render("tpl")`）を採る**。function 形 `render("tpl", subject)` より既存 helper のパイプ様式に一貫し、値変換のふりも動詞で操作を signal できる。`this` は `@pass_context`（Jinja2）/ `@pass_state`（minijinja）で取得。
- **split 時の `""` を静かに保つ（診断化しない）**。inline / split の二挙動は **edition（Web=split / Book=inline）の継ぎ目そのもの**で、`""` は「独立ページへ昇格した内容を親が優雅に省く」load-bearing 機構（[paging-spec の分割ルール](40-paging-spec)）。合成位置での split-render を診断化すると同一記述の両版両立が壊れる。

移行は二段: **P7** で filter 形を追加（`{% render %}` タグは併存のまま）、showcase + dev-docs + 稼働プロジェクトを out-of-band で filter へ移す。移り切ったら **P8** でタグと `RenderExtension` を撤去し filter 形へ一本化する（Q1 前、公開語彙にタグ遺産を残さない）。`mood_view` エイリアス廃止（P5）と同じ要領。
