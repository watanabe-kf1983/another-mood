# Inter-Stage Communication (appendix)

[Inter-Stage Communication](../../../20-design/40-communication/index.md) の背景。

## ステージ間の受け渡しを hardlink にした理由

受け渡しはディレクトリの写しで行う——ステージは temp に書いて出力へ同期し、下流は上流の出力の時点コピーを取る——ので、一つのファイルは出力に届くまでに何度も hop する（ステージの temp → 出力、上流の出力 → 下流の入力、edition ごとの publish 出力）。コピーで運ぶと hop の数だけバイト列が複製され、大きな blob を持つsbdb プロジェクトでは watch の再実行のたびにそれを払う。hardlink で運べば実コピーは contents → workspace の境界の 1 回に収まる (PR #336)。

### 効果 (実測)

showcase/music (100MB blob・2 edition) を同一 FS 上で計測すると、build 一巡で materialize される blob の実バイトコピー (distinct inode) は **12 → 3**。3 の内訳は境界コピー 1 + Hugo の static→destination 内部コピー 2 (制御外)。md レーンは境界の 1 inode を publish 出力まで hardlink 共有する。warm 無変更リビルドは境界コピーも再利用し実コピー 0。publish 先が別 FS の場合のみ publish 境界で実コピーが復活する (publish の増分化は範囲外の後続候補)。
