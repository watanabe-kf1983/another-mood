# Normalizer

## Internal Design

### 正規化スコープと catalog 境界

正規化スコープは catalog 化スコープと一致させる。境界外で walker が走ると、新規変換の追加で silent に壊れる latent risk が生じる。

- `content_normalizer`: user schema 全体が catalog 範囲 (`iter_normalized` で深く正規化)
- `query_deriver`: top-level dict のみが catalog 範囲 (`_iter_top_level` で dict→list 変換 + `normalize_query` による DSL の sugar→canonical 変換。catalog 化はしない)

### dict-pattern の synthetic id は常に string

`additionalProperties` を持つオブジェクトを `[{"id": <key>, ...}]` 配列に正規化する際、`id` は `str(key)` でコエースする。YAML は int/bool キー (`10:`) を natively 許すが、以下の理由で string に揃える:

1. **JSON は string キーしか持たない** — YAML キーは JSON 由来の正規化先には乗らない型を取りうるが、永続化形式 (`save_model` で書き出す YAML) は JSON 互換を保つ
2. **catalog 宣言が `id: string`** ([schema-spec.md](20-schema-spec.md) Entity 名節) — 宣言とデータ実体の型を一致させる
3. **x-ref ターゲット集合の型統一** — FK 検査が string-only で完結する (schema-schema は x-ref を type=string のみ許容)
4. **アンカーパス生成の一貫性** — entity ページのパス・アンカーパス生成器が常に string 入力を仮定できる

この normalization contract は user 向け reference には書かない (JSON 由来の自然な前提であり、明文化が逆にノイズになる)。surface したら `docs/reference/schema.md` の dict-pattern 節に注釈を足す。

## Proposals

### バイナリファイルの取り扱い (H1, H2)

> H1 (仕様確定) 済み・H2 (実装) 未着手。Phase 13 タスク [H1, H2](node:/tasks/H/tasks/H1)。

`contents_dir` に置かれた YAML・Markdown 以外のすべてのファイルを、内蔵コレクション **`blob`** のレコードとして扱う。名前が指すとおり正確なスコープは「バイナリ」ではなく「**ツールが解釈しない不透明なファイル**」であり、テキストファイル (.csv, .txt, .svg 等) も含む。M6/M7 の blob marker (`x-mood-blob`、walker から opaque) と同じ概念系。

#### 背景: 要求

- ソフトウェア開発ドキュメントには、mermaid.js で表現できない図表・画面レイアウト等を画像として `![]()` で埋め込む必要がある (コア要求)
- 画像に限らず、動画へのリンク、ファイル仕様書からのサンプル実物 (Excel / CSV 等) へのリンクも同様に扱う
- 出力ドキュメントの自己完結・可搬性がツールの提供価値 — 外部アップロード先へのリンクで代替しない。帰結として各 edition 出力へバイナリリソースを全コピーする
- prose の編集時 (エディタ上) から、相対パスで `![]()` / `[]()` が機能すること
- YAML レコードから id で参照でき、クエリで join できること (例: 画面エンティティ → 画面イメージ図)

なお「コンテンツではなくテンプレートの付随物となる静的アセット」(テンプレートが HTML 化したときの CSS 等) は将来の別区分であり、contents には置かず、本仕様の対象外。

#### External Design

**スコープと除外規則** — contents_dir 内の YAML / Markdown 以外の全ファイルが blob になる (従来の silent skip は廃止)。不明拡張子も skip せず `application/octet-stream` で通す。除外はドットファイル・ドットディレクトリのみ (`.DS_Store`・エディタの隠しファイルを一点でカバーする SSG 慣行)。除外・許可リストの設定機構は実需が出てから足す (加算的なので後入れで手戻りしない)。

**データモデル** — レコードは `{id, body: {mime_type}}`。

- id は**拡張子込み**の contents 相対パス。拡張子を落とすと `fig.png` / `fig.jpg` が衝突する。prose の拡張子なし id は「.md が唯一の拡張子だから成立した省略」であり、blob には適用しない
- `mime_type` は拡張子から導出 (stdlib `mimetypes`)
- バイト列はデータモデルに載せない (base64 は肥大・メモリ・diff 破壊で却下)。**絶対パスも持たせない** — id が contents 相対パスそのものなので、コピー役は config から実パスを復元できる。絶対パスは診断ビュー・中間 YAML に環境固有情報を焼き付け、可搬性と衝突する
- body を Typed Value 形 (`mime_type` のみ、`content` は省略) に保つのは prose との構造対称性のため。将来 text/html 等で inline content を持つ余地を残す

##### 背景: prose と別コレクションにする理由

prose は `{% mood_view %}` で埋め込めるレンダリング可能な本文を持つ「ページ素材」、blob は「参照されるリソース」で、テンプレート上の役割が根本的に違う。別コレクションなら、既存の prose を iterate するテンプレート群にバイナリレコードが混入する互換問題もそもそも発生しない。(旧 H3「prose へ統合・改名」案はこの判断で棄却 — 次節)

**パス解決 (相対リンク → node:)** — prose body 内の in-tree 相対リンクのうち .md 以外のターゲット (`![]()` 画像・`[]()` リンクとも) は、preprocess で `node:/blob/<id>` へ正規化し、generate の relink が表示ページ相対 URL へ解決する。既存の .md → `node:/prose/` 機構への相乗り。編集時のエディタプレビューは、相対パス authoring そのものが保証する。contents 外への脱出・スキーム付き・絶対パスは従来どおり verbatim。未解決参照は [anchor-spec.md の未解決契約](../70-generator/20-anchor-spec.md#未解決参照の扱い) に従う。

**YAML からの参照** — `x-ref` で blob id を指す。ツール側の仕事は blob をデータカタログにエンティティ登録するところまでで、それにより既存の FK 検査がそのまま効く。x-ref をどう張るかは利用者のスキーマ設計の問題。

**テンプレートからの参照** — href 系フィルタ (node → URL 解決) で参照する。画像ビルダ関数等の追加ヘルパは実需が出てから。

**出力配置** — 各 edition ルート直下に contents 相対パスをミラー。md 出力 (out_dir) と html 出力 (render_dir) の両方に置く。参照の有無に関わらず全 blob をコピーする (到達可能性解析はしない)。

#### Internal Design 方針

**Composer への受け渡し** — composer を通るのはメタデータレコードのみ。バイト列は normalize にも compose にも入らない。

**バイトの旅程** — 注入点は generate。`contents_dir + id` からバイトを読み、各 edition ツリーへミラーする。

- 背景: generate は templates_dir / reports_file を user 入力として直接読む先例があり、後段ステージの user 入力読みはアーキテクチャの範囲内。edition ルートがどこかの知識は generator の所有物で、後段で注入すると再導出が要る。generate の一点注入なら、下流 2 レーン (md publish 行き / Hugo contentDir 行き) は既存の運搬機構が自動継承し、`mood watch` (G9 以降 publish なし) のライブプレビューにも Hugo contentDir 経由でバイトが届く
- 注入は**増分 sync** (size + mtime 比較)。clear-and-copy だと watch でテンプレート一文字の変更ごとに動画が全コピーされる
- contents → ワークスペースは実コピーとする。ソースへのハードリンクは禁止: inode 共有のため、in-place 上書き保存するツール (vim 既定・ffmpeg 等) でソースを更新すると出力が黙って変わる・書きかけが見える。ワークスペース内ホップのハードリンク化は H2 の最適化自由度 (Windows/NTFS でも `os.link` 可、EXDEV 等は copy fallback が定石)

#### 受け入れ確認

- showcase/music: アルバムごとのジャケット写真を YAML レコード (x-ref) + テンプレートで表示
- prose `![]()` 相対パス埋め込みの例 — 全 body が単一ページに inline される book edition でのリンク解決を含めて確認する (機構的に最も壊れやすい経路)

#### H2 実装時の確認事項

- Hugo が .html / .md 拡張子の blob を content として解釈しないよう封じる方法 (「HTML をページとして扱う」ユースケースは次節の後継アイデア)
- `load_model` がバイナリ混在ツリーで YAML 以外を無視すること
- blob ミラーパスとテンプレート由来ページパスの衝突検査
- prepare_render の in-place sync (`copy2`) とハードリンクの相性 (truncate が共有 inode を壊す)・削除プレースホルダ (`write_text`) が blob パスへ書かれる問題
- C7 (FS-safe パス) / D10 (NFC) の blob ファイル名への適用

### 散文サブシステムの一般化 (H3)

> **棄却** — 旧案「エンティティ名 `prose` を媒体非依存な名前に改名し、バイナリファイルを統合する」は H1 の仕様確定で棄却した。

理由は上記「背景: prose と別コレクションにする理由」のとおり。prose と blob はテンプレート上の役割が違い、統合すると既存テンプレートの iterate を壊すだけで得るものがない。

後継アイデア (未タスク化): text/html の blob を「ページとして解釈する」ユースケース (画面イメージ図を HTML で作る等)。body Typed Value の mime_type 分岐 (text/markdown 以外の本文型) の延長として設計する余地がある。実需が surface してから検討する。

### Unique 制約 (D8, D9)

追加の Unique 制約（id 以外のフィールドに対する一意性）の宣言。Phase 10 タスク [D8, D9](node:/tasks/D/tasks/D8)。

### 正規化スコープと catalog 境界 (M6, M7)

M5 で確立した境界 (Internal Design 参照) を、ad-hoc 実装から schema 上のマーカー駆動の一般機構に置き換える後続段階。

#### 段階 2 (M6): blob marker 機構の導入 (内部 schema 専用)

M5 の ad-hoc な「浅い正規化」を、schema 上のマーカーで表現できる一般機構に置き換える。マーカーを見ると `build_schema_tree` は `BlobNode` (新規) を emit、`normalize_data` はデータをパススルー、というルール。

マーカー syntax の候補:

| 案 | 内容 | 評価 |
|---|---|---|
| `additionalProperties: true` 流用 | JSON Schema 既存語彙の再解釈 | 意味的整合 (extras OK = opaque)。`additionalProperties: <schema>` (dict-pattern) や `false` (strict) との分岐ロジック増 |
| **`x-mood-blob: true` custom annotation** | JSON Schema validator が未知 key として無視 | 意図が surface に出る、独立 semantic、将来拡張余地あり。**本命** |

この段階では `query-schema.yaml` の `whereClause` 等にマーカーを付け、M5 で導入した ad-hoc な浅い正規化 (`_iter_top_level`) を marker 駆動に置き換える。**`schema-schema.yaml` には触れない (内部 schema 専用)**。

具体的な改修対象:

- `schema_tree.py`: マーカー検出時に `BlobNode` を emit、内部再帰なし
- `normalize_core.py`: マーカー検出時はパススルー
- `query-schema.yaml`: `whereClause` 等に `x-mood-blob: true` 付与
- `data_catalog.py`: `BlobNode` の catalog 表現

#### 段階 3 (M7): user schema への解放

M6 の機構を `schema-schema.yaml` の `if/then/else` で user schema からも宣言できるようにする。骨子:

```yaml
$defs:
  maybeBlobOrStrict:
    if:
      type: object
      required: [x-mood-blob]
      properties: { x-mood-blob: { const: true } }
    then:
      $ref: "#/$defs/blobSchema"
    else:
      $ref: "#/$defs/jsonSchemaSubset"

  blobSchema:
    type: object
    required: [type, x-mood-blob]
    properties:
      type: { const: object }
      x-mood-blob: { const: true }
    # additionalProperties 制約を外す → oneOf / $ref 等の JSON Schema 構文を許容
    # → validator は標準通り解釈、walker は opaque

  jsonSchemaSubset:
    # 既存の strict subset、ただし再帰先を maybeBlobOrStrict に切替
    ...
```

メタドキュメント (`__entity_defs`) で blob 属性の表示形式を整え、`docs/reference/schema.md` に解説追加。

実需確認 (showcase / dev-docs での「ここは blob にしたい」具体ニーズ、または user からのリクエスト) が surface してから着手。現時点では明確な user requirement なし、design 議論のみ完了。

#### 走査の非対称性との関係

blob 内部は walker (build_schema_tree, normalize_data, query DSL の参照解決) いずれからも opaque。これは [queries-spec.md「背景: 走査の非対称性を設計原則として確立した」](../60-composer/10-queries-spec.md#背景-走査の非対称性を設計原則として確立した) の「nested array に潜るのは `flatten:` 系のみ」と同質の制約として扱う。
