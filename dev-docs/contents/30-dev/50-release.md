# リリースフロー

リリース = version 確定 + git tag push。main は trunk のまま、「main マージ = リリース」
ではない。リリースに要る判断と記述はすべて PR 時点で置き、リリース時はその消化
（読む・打つ・貼る）だけ——役割による手順の分岐はない。
設計判断の背景は [release-background.md](55-release-background.md)。

## バージョニング

- 版宣言の正本は git tag ただ一つ。pyproject の version は hatch-vcs が tag から
  導出する（設営は [T3](node:/tasks/T/tasks/T3)——下記未実装）。bump コミットという
  工程はない
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

### Release-Note トレーラー

告知したいことのある PR は、PR 本文の末尾に行頭から一行書く:

    Release-Note: feature: mood tap outputs JSON

- key は `Release-Note`、マークは breaking / feature / fix の三値、本文は英語一行。
  本文は利用者向けの告知文であり、タスク ID 等の内部語彙は書かない。
  必ず行頭に置く（リリース手順 1 の収集が行頭 grep のため）
- breaking のみ義務。feature / fix は裁量
- feature / fix の規準は「docs/reference の**約束の集合が増減したか**」。増減したら
  feature（既存挙動の新規文書化も、契約外を契約内に入れる拡張なので feature）。
  同じ約束の言い直し・明確化・構成整理は fix 以下。この判定は意味判断であり、
  機械検査せず作者に委ねる

### 破壊的 PR の義務

破壊的 PR（フォーマット破壊・ツール破壊とも）は、以下をすべて自身に含める。
breaking トレーラーだけが PR 本文に書かれ、他はレビュー対象のリポジトリ内容:

1. **非互換注記** — 非互換に書き換えた docs/reference の章に「この章の契約が最後に
   非互換に動いた版」を記す一行を書く（または更新する）。値は、フォーマット章
   （schema / view / template / manifest）は世代番号、ツール章（cli 等）は日付か
   PR 番号（リリース版番号は tag を打つ瞬間まで存在しない）。貼付は lazy——全章に
   貼って回らず、最初の破壊的編集が最初の注記を書く。注記の不在は
   「一度も壊れていない」の表明として正しい
2. **移行手順ほか（フォーマット破壊のみ）** — 利用者向けの移行手順を docs に書く
   （正本はリリースノートではなく docs。置き場所は該当章の注記の近傍を第一候補に、
   最初の破壊的変更時に確定）。および世代番号まわりの追随一式
   （[sbdb-manifest](node:/prose/20-design/20-app/60-sbdb-manifest) の管轄）
3. **breaking トレーラー** — 上記書式で PR 本文末尾に

## リリース手順

役割によらず単一。main へのコミットはない。5 分で回る軽さを目標とする。

```
1. 次版番号を導出: 前回 tag 以降のトレーラーを収集
   （git log <前回タグ>..HEAD --format=%B | grep -E '^Release-Note: '）
   し、マークの最高位を取って写像表に通す
   検算: git log <前回タグ>..HEAD の一読で宣言の抜けを検める（破壊の記録漏れは
   PR 側の規律が塞ぐ。ここで拾うのは feature マークの書き忘れ程度）
2. tag push → ワークフロー完走（build → PyPI publish → GH Release 自動作成）の確認
3. 生成された GH Release の冒頭に、手順 1 の収集結果を整形して足す——オマケも
   移行手順のポインタも同じ動作（収集が空なら何も無し）
```

## 未実装（各タスクの実装時に消し込む）

### T3 — tag 駆動 publish ワークフロー

まず方式 B の導入設営（実機検証済み）:

- hatchling に hatch-vcs を追加し `dynamic = ["version"]` 化
- 変則 tag（`v0-ts-baseline` 等が既存）対策の tag パターン設定を保険で入れる
- `tool.uv.cache-keys` に git キーを追加（editable 環境の `importlib.metadata` が
  古い版のまま残るのを防ぐ）
- ci.yml と publish ワークフローの checkout を `fetch-depth: 0` に（shallow clone
  では版導出できず `uv sync` のビルドが落ちる）
- showcase / dev-docs のマニフェストから `tools:`（minimum_version）ブロックを削除
  （[sbdb-manifest](node:/prose/20-design/20-app/60-sbdb-manifest) 側で決定済みの
  「置かない」の実施）
- `[project.urls]` に Changelog リンク（GH Releases へ）を足す（PyPI には
  リリースノートの表示面がないため）

その上で publish ワークフロー:

- tag push（`v*`）契機: build → PyPI publish → GH Release 作成
- 認証は trusted publishing（プロジェクトは 0.1.0 手動 publish で実在するため
  通常登録。以後 API token は不要）
- リリースノートは GH 自動生成（PR タイトルの束ね）が台帳層を担う。ラベル別の
  節分けはしない。外部向けの体裁格上げ判断は [Q7](node:/tasks/Q/tasks/Q7)

保留装置（建てる契機だけ記録して封印）:

- **tag sanity check**（ワークフロー冒頭で tag をトレーラーの最高位と突き合わせ）—
  tag の打ち間違いが実際に起きたとき
- **Release 本文へのトレーラー自動転記** — 手作業の貼り付けが煩わしくなったとき
- **自動 tag**（トレーラーを読んで機械が tag を打つ）— リリース頻度が裁量判断を
  上回ったとき

### T4 — PR lint ワークフロー

既存シグナル同士の決定的な突き合わせのみ。「内容が破壊的かどうか」の意味判定は
しない。出口は二種:

- **fail はトレーラー書式検査のみ**: PR 本文に Release-Note 風の行があれば key の
  綴り・マーク語彙・書式を検証し、ニアミス（`Release-Notes:` 等）も狭いパターンで
  検知して落とす。PR 本文の編集でも再検査する（opened / edited / synchronize）
- **注意喚起は非ブロックの sticky コメント**（一件に集約、コピペ可能な suggest と
  DEVELOPMENT.md へのポインタ付き）。トリガ二つ、文面の強度は前者 > 後者:
    - 世代宣言ファイル（V8 で切り出す専用モジュール）に diff ∧ breaking
      トレーラー無し →「フォーマット破壊に見える。breaking は義務」
    - docs/reference に diff ∧ トレーラーゼロ →「約束の集合が増減したなら
      feature / fix をどうぞ。言い直しだけなら無視してよい」

保留装置（建てる契機だけ記録して封印）:

- **世代チェックの集合比較化**（ファイル diff 検知を、両端点から対応集合を抽出して
  脱落を検知する方式に格上げ）— 複数世代並行サポート解禁のとき
- **世代側注意喚起の fail 格上げ** — 外部コントリビュータを受け入れたとき
- **docs 側注意喚起の fail 格上げ**（トレーラー宣言の義務化。マーク自体は作者選択の
  まま）— 1.0.0 で feature / fix の桁が分かれ、賭け金が生まれたとき
- **差分ハーネス**（merge-base 時点の showcase + dev-docs ソースに旧新両版の mood を
  かけ、出力 diff を Warn として PR に提示）— 外部コントリビュータを受け入れて
  全 diff を精読しなくなったとき、または最初の silent 破損事故が起きたとき

### V8 — 世代宣言の切り出し

SUPPORTED_SBDB_VERSIONS を専用モジュールに切り出す（T4 の diff 検知対象）。
