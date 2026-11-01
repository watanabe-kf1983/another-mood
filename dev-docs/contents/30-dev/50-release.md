# リリースフロー

リリース = version 確定 + git tag push。main は trunk のまま、「main マージ = リリース」
ではない。リリースに要る判断と記述はすべて PR 時点で置き、リリース時はその消化
（読む・打つ・貼る）だけ——役割による手順の分岐はない。
設計判断の背景は [appendix](../90-appendix/30-dev/50-release.md)。

## バージョニング

- 版宣言の正本は git tag ただ一つ。pyproject の version は hatch-vcs が tag から
  導出する。bump コミットという工程はない
- リリース tag は `vN.N.N` 形（ハイフンを含まない）。リリースワークフローの発火条件と
  hatch-vcs の版導出（pyproject の describe フィルタ）がこの形を共有する。リリースでない
  目印 tag は `milestone/` 名前空間に置く
- リリースの役割は三値——破壊 / 互換・機能 / 互換・修正。破壊は二種の総称:
    - **フォーマット破壊** — サポート世代の脱落（old_supported − new_supported ≠ ∅。
      世代の**追加**自体は破壊ではない。世代運用は
      [sbdb-manifest](node:/prose/20-design/20-sbdb-project/20-sbdb-manifest) の管轄）
    - **ツール破壊** — CLI 等、ツールの利用者向け契約の破壊
- 役割から版番号の桁への写像。桁の対応はこの表だけが持ち、他の記述は役割語で書く:

  | 役割 | 0.x 期（現行） | 1.0.0 以降 |
  |---|---|---|
  | 破壊 | 0.MINOR+1 | MAJOR+1 |
  | 互換・機能 | 0.x.PATCH+1 | MINOR+1 |
  | 互換・修正 | 0.x.PATCH+1 | PATCH+1 |

- リリースの契機は裁量（少なくともローンチまで）。1.0.0 はローンチ
  で刻む
- 破壊的 PR をマージすると、以後の main からは互換リリースが打てなくなる。
  「次のリリースを破壊リリースにする覚悟ができたときにマージする」。
  旧系列への修正需要が実際に発生したら、過去 tag から遡及ブランチを切って
  cherry-pick する（`git switch -c release-0.X v0.X.Y`）

## PR 側の規律

PR タイトルにタスク ID 等の内部語彙は書かない。タイトルは自動生成の台帳にそのまま
載り、ハイライトの見出しも務める——どちらも利用者が読む面で、タスク ID の宛先では
ない。タスク ID は PR 本文に書く。

### Release-Highlight トレーラー

リリースノート冒頭のハイライトに載せたい PR は、PR 本文の末尾に行頭から一行書く:

    Release-Highlight: fix

- key は `Release-Highlight`、kind は breaking / feature / fix の三値。kind 以外は
  書かない（見出しは PR タイトルが務める）。必ず行頭に置く（リリース手順の収集が
  行頭 grep のため）
- breaking のみ義務。feature / fix は裁量
- feature / fix の規準は「docs/reference の**約束の集合が増減したか**」。増減したら
  feature（既存挙動の新規文書化も、契約外を契約内に入れる拡張なので feature）。
  同じ約束の言い直し・明確化・構成整理は fix 以下。この判定は意味判断であり、
  機械検査せず作者に委ねる
- 一つの PR が複数の kind を宣言してよい（一行に一つ）

### 説明セクション

PR タイトルを超える説明は、PR 本文にセクションとして書く。見出しは kind の組ごとに
一つで、リリースノートの節に対応する。PR の記入面と Release の節を一対一にし、
セクションと kind の食い違いを lint が機械で拾えるようにするための分け方:

| 見出し | 伴う kind | 書くか | Release での節 |
|---|---|---|---|
| `## Breaking change` | breaking | 義務 | Breaking changes |
| `## Release highlight` | feature / fix | 裁量 | Highlights |

- 自由形式の利用者向け英文で、タスク ID 等の内部語彙は書かない。リリース時に
  Release 冒頭へそのままコピペされる
- `## Breaking change` には移行の要約と docs の移行手順へのポインタを書く
- 一つの PR が両方を持ってよい。破壊と引き換えに機能を入れる PR なら、移行を前者、
  新しくできることを後者に書き、breaking と feature を併記する

### 破壊的 PR の義務

破壊的 PR（フォーマット破壊・ツール破壊とも）は、以下をすべて自身に含める。
トレーラーと `## Breaking change` セクションだけが PR 本文に書かれ、他はレビュー
対象のリポジトリ内容:

1. **移行手順ほか（フォーマット破壊のみ）** — 利用者向けの移行手順を docs に書く
   （正本はリリースノートではなく docs。置き場所は最初の破壊的変更時に確定）。
   および世代番号まわりの追随一式——コードの対応集合・scaffold 生成物・
   showcase / dev-docs のマニフェスト。更新漏れは、ビルドとテストが世代番号に
   張り付いているため既存 CI が落とす
2. **`Release-Highlight: breaking` トレーラーと `## Breaking change` セクション** —
   上記書式で PR 本文に

### lint による自動検査

PR を開く・再開する・本文を編集する・push する、のいずれでも `PR lint` ワークフローが
走り、上の規律のうち機械で決まる部分だけを見る。既存シグナル同士の突き合わせに徹し、「内容が破壊的かどうか」の
意味判定はしない。出口は二種——書式・整合の決定的な違反は fail、diff とトレーラーの
噛み合わせは非ブロックの sticky コメントで注意喚起。説明セクションと kind の対応
（上表）は整合に属し、どちらの向きの食い違いも fail。

## リリース手順

役割によらず単一。main へのコミットはない。5 分で回る軽さを目標とする。
手で入れる値は次版番号ただ一つで、前回 tag は導出する（打ち間違いの余地を残さない）。

### 1. 次版番号を導出

前回 tag を導出し（tag を打つ前に取る。後だと自分自身を指す）、以降の kind を収集して
最高位を写像表に通す。

```bash
PREV=$(git describe --tags --abbrev=0 --match 'v[0-9]*.[0-9]*.[0-9]*' --exclude '*-*')
git log "$PREV"..HEAD --format=%B | grep -E '^Release-Highlight: '
```

検算として一読し、宣言の抜けを検める（破壊の記録漏れは PR 側の規律が塞ぐ。ここで
拾うのは feature kind の書き忘れ程度）。

```bash
git log "$PREV"..HEAD --oneline
```

### 2. tag を打って push

導出した番号を `NEW` に置く。tag は lightweight——tag オブジェクトを読むものは無く、
リリースの記述と日付は GH Release が持つ（署名を入れるなら annotated へ改める）。

```bash
NEW=v0.X.Y
git tag "$NEW" && git push origin "$NEW"
```

ワークフロー完走（build → PyPI publish → GH Release 自動作成）を確認する。

### 3. ハイライトを GH Release の冒頭に足す

収集が空なら何も無し。材料は次の出力。長文で折り返しが煩わしければ原文は PR ページ
（タイトル末尾の #番号）にある。

```bash
git log "$PREV".."$NEW" --grep='^Release-Highlight: ' --format='=== %s%n%n%b'
```

冒頭に次の二節を、この順で置く。該当する PR の無い節は置かない。各節の中は PR 番号順:

- `## Breaking changes` — breaking を宣言した PR。PR タイトルを `### タイトル (#番号)` の
  見出しにし、`## Breaking change` セクションの本文を続ける
- `## Highlights` — feature / fix を宣言した PR。`## Release highlight` セクションを
  持つ PR は同じく `###` 見出しと本文、持たない PR はタイトル行を箇条書き一行にする
  （本文の無い項に見出しを与えると中身の無い節ができる）。`###` 項目があるときは
  箇条書きを `### Other highlights` の下に置く（無いと直前の項目の一部に見える）

本文中の相対リンクは Release ページから解決できないので、tag 固定の絶対 URL
（`https://github.com/<owner>/<repo>/blob/<NEW>/docs/...`）に直す。

CLI で足すなら、自動生成部を取り出し、冒頭にハイライトを書き足してから戻す。本文は
丸ごと置換されるため、読まずに書き戻さない。`gh` はリポジトリ内で実行する（作業
ディレクトリを移すと `not a git repository` で落ちる）。

```bash
gh release view "$NEW" --json body --jq .body > /tmp/notes.md
# /tmp/notes.md の冒頭にハイライトを書き足す
gh release edit "$NEW" --notes-file /tmp/notes.md
```
