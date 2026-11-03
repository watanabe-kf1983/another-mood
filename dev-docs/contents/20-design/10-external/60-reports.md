# Reports

`docs/reference/reports.md` の契約の外で、意図して保つ振る舞い。出力ツリーのうち `__db/` の中身は [DB 自己記述](../30-pending/75-meta-documentation/10-database-information.md)、`__build_info/` と `__warnings/` は[奥付](../30-pending/75-meta-documentation/20-build-information.md)と[ビルドレポート](../30-pending/75-meta-documentation/30-build-report.md)が扱う。

本文で使う語:

- **report** — 利用者のテンプレートがデータから描く一組の出力。`definition/reports.yaml` が設定する（`docs/reference/reports.md`）
- **edition** — 同じ report の体裁違いの出力。違いは `file_per`（どの型のノードを別ファイルに分けるか）だけ（同 Editions）
- **form A / form B** — `reports.yaml` の二つの書き方。form A はトップレベルに `file_per` を書き、`default` という名の一つの edition になる。form B は `editions:` に名前付きで複数書く（同 Editions）
- **メタ edition** — スキーマとビューの定義からツールが自動で描く `__db/` のページ群。edition と同じ機構で描く
- **マウント** — 出力ルート直下で、edition やシステム生成の出力に与えるディレクトリ。`{edition}/` と `__db/` など
- **ノード / アンカーパス / 主題 / blob** — [Template](50-template.md) の語。アンカーパスはノードの住所で、`/` 区切りの各セグメントは percent-encode 済み。主題は一回の描画の対象で、分割ページの主題がそのページを決める。blob はファイルを表す組み込みの entity
- **表紙** — 出力ルートの `index.md`。Reports と DB 自己記述への入口

## edition

### edition は同じ report の体裁違いで、環境ごとに選ぶ profile ではない

宣言された edition はすべて一回のビルドで生成され、`{outDir}/{edition}/` に横並びに置かれる。想定している使い分けは、web 向けにはページを細かく分け、印刷向けには一ファイルにまとめる、というもの。両方を同時に欲しいのが普通なので、どれか一つを選ぶ口は要らない。

ビルド時に一つを選ぶ `--edition` のようなオプションは持たない。レンダラやフォーマットの違いを表す軸でもなく、Markdown から HTML への変換は全 edition で同じ。契約が言う「side by side」は成果物が並ぶ意味であって、並行実行の意味ではない。

## 出力パス

### ファイル名はアンカーパスをセグメント単位で percent-decode し、ファイルシステムが持てない文字だけ `~XX` に逃がす

分割したページのパスは主題のアンカーパスから導く（契約の Output path）が、住所の文字列をそのままファイル名にはしない。セグメントごとに percent-decode する。ブラウザも静的サーバも GitHub も Hugo も、URL を decode してからファイルを探すため。

セグメント単位で decode するので、id の中の `%2F` が区切りに化けない。decode で現れた `/` は次の規則で `~2F` になる。

decode で現れる文字のうち、ファイルシステムが持てないもの（`/` を含む Windows の予約文字、`~` 自身、末尾の `.` と空白）だけは `~XX` に逃がす。

`%XX` にしないのは、Hugo がファイル名の `%XX` を URL エンコード済みとみなして温存するため。サーバは URL を decode してからファイルを探すので、`%XX` を名に持つファイルには、どの URL からも届かない。

リンクの URL もこのファイル名から作る（`href` はページのパスを percent-encode する）ので、`~XX` のファイルへは `~XX` の URL で届く。アンカーパスが URL に現れるのは fragment の部分だけ。

blob の出力先（各 edition のルート直下の `blob/` に写す。[内部構造の約束](../20-internal/10-architecture.md#ステージをまたぐ約束)）と edition のディレクトリ名も同じ規則で名前を得る。文字単位で潰せない問題（パス長の超過、Windows のデバイス名）は escape ではなく書き出し側が別に対処する（`shared/windows_reserved_name.py`）。

### 各 edition とマウントは、自己完結した相対リンクの部分木

出力ルートの構成:

```
{outDir}/
  index.md          ← 表紙。project 名、Reports、Database Information
  default/          ← 利用者の edition（form B なら web/ print/ 等）
  __db/             ← DB 自己記述（メタ edition のマウント先）
  __build_info/     ← 奥付
  __warnings/       ← 警告（あるときだけ）
```

リンクの URL はページ相対なので、`{edition}/` や `__db/` のマウント接頭辞はリンクに現れない。各 edition は単独で持ち出して別の場所に置いても壊れず、マウントはリンク解決に透過。

表紙は edition ではなく、一回だけ描く薄いページ。`__db/` は edition の機構で描くが、体裁違いの report ではないので、表紙では Reports に並べず別のエントリに置く。
