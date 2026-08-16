# リリースフロー

リリース = version 確定 + git tag push。main は trunk のまま、「main マージ = リリース」
ではない。リリースに要る判断と記述はすべて PR 時点で置き、リリース時はその消化
（読む・打つ・貼る）だけ——役割による手順の分岐はない。
設計判断の背景は [release-background.md](55-release-background.md)。

## バージョニング

- 版宣言の正本は git tag ただ一つ。pyproject の version は hatch-vcs が tag から
  導出する。bump コミットという工程はない
- `v` で始まる tag はリリース専用。リリースワークフローの発火条件と hatch-vcs の
  版導出がともにこの前提に立つ。リリースでない目印 tag は `milestone/` 名前空間に置く
- リリースの役割は三値——破壊 / 互換・機能 / 互換・修正。破壊は二種の総称:
    - **フォーマット破壊** — サポート世代の脱落（old_supported − new_supported ≠ ∅。
      世代の**追加**自体は破壊ではない。世代運用は
      [sbdb-manifest](node:/prose/20-design/20-app/60-sbdb-manifest) の管轄）
    - **ツール破壊** — CLI 等、ツールの利用者向け契約の破壊
- 役割から版番号の桁への写像。桁の対応はこの表だけが持ち、他の記述は役割語で書く:

  | 役割 | 0.x 期（現行） | 1.0.0 以降 |
  |---|---|---|
  | 破壊 | 0.MINOR+1 | MAJOR+1 |
  | 互換・機能 | 0.x.PATCH+1 | MINOR+1 |
  | 互換・修正 | 0.x.PATCH+1 | PATCH+1 |

- リリースの契機は裁量（少なくともローンチまで）。1.0.0 はローンチ
  （[Q3](node:/tasks/Q/tasks/Q3)）で刻む
- 破壊的 PR をマージすると、以後の main からは互換リリースが打てなくなる。
  「次のリリースを破壊リリースにする覚悟ができたときにマージする」。
  旧系列への修正需要が実際に発生したら、過去 tag から遡及ブランチを切って
  cherry-pick する（`git switch -c release-0.X v0.X.Y`）

## PR 側の規律

PR タイトルにタスク ID 等の内部語彙は書かない。タイトルは自動生成の台帳にそのまま
載り、`## Release highlight` セクションを持たない PR ではハイライトの見出しも務める
——どちらも利用者が読む面で、タスク ID の宛先ではない。タスク ID は PR 本文に書く。

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
- PR タイトルを超える説明を載せたいとき（主に breaking——移行の要約と docs への
  ポインタ）は、PR 本文に `## Release highlight` セクションを書く。自由形式の
  利用者向け英文で、タスク ID 等の内部語彙は書かない。リリース時に Release 冒頭へ
  そのままコピペされる

### 破壊的 PR の義務

破壊的 PR（フォーマット破壊・ツール破壊とも）は、以下をすべて自身に含める。
トレーラーと `## Release highlight` セクションだけが PR 本文に書かれ、他はレビュー
対象のリポジトリ内容:

1. **移行手順ほか（フォーマット破壊のみ）** — 利用者向けの移行手順を docs に書く
   （正本はリリースノートではなく docs。置き場所は最初の破壊的変更時に確定）。
   および世代番号まわりの追随一式
   （[sbdb-manifest](node:/prose/20-design/20-app/60-sbdb-manifest) の管轄）
2. **`Release-Highlight: breaking` トレーラーと `## Release highlight` セクション** —
   上記書式で PR 本文に。セクションには移行の要約と docs の移行手順へのポインタ

### lint による自動検査

PR の開閉・本文編集・push で `PR lint` ワークフローが走り、上の規律のうち機械で
決まる部分だけを見る。既存シグナル同士の突き合わせに徹し、「内容が破壊的かどうか」の
意味判定はしない。出口は二種——書式・整合の決定的な違反は fail、diff とトレーラーの
噛み合わせは非ブロックの sticky コメントで注意喚起。

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

収集が空なら何も無し。材料は次の出力——`## Release highlight` セクションを持つ PR は
そのセクションを見出し付きでコピペし、無い PR はタイトル行を箇条書き一行にする
（本文の無い項に見出しを与えると中身の無い節ができる）。長文で折り返しが煩わしければ
原文は PR ページ（タイトル末尾の #番号）にある。

```bash
git log "$PREV".."$NEW" --grep='^Release-Highlight: ' --format='=== %s%n%n%b'
```

CLI で足すなら、自動生成部を取り出し、冒頭にハイライトを書き足してから戻す。本文は
丸ごと置換されるため、読まずに書き戻さない。`gh` はリポジトリ内で実行する（作業
ディレクトリを移すと `not a git repository` で落ちる）。

```bash
gh release view "$NEW" --json body --jq .body > /tmp/notes.md
# /tmp/notes.md の冒頭にハイライトを書き足す
gh release edit "$NEW" --notes-file /tmp/notes.md
```
