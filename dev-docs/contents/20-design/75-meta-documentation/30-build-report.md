# ビルドレポート

ビルドで何が起きたかを著者に見せる出力。警告は `__warnings/` に置き、エラー時は表紙 (`index.md`) をビルド失敗ページに置き換える。どちらも Generator の直後の Reconcile ステージが置く。

## Internal Design

### Reconcile

Reconcile は Generator の直後に位置するステージで、「Generator の出力（あるべき姿）」と「上流から伝播してきた `BuildReport`（実際に何が起きたか）」を突き合わせ、ユーザに見せる最終出力を確定する役割を持つ。

- エラー無し: Generator の出力をそのまま reconcile の出力ディレクトリに通す（pass-through）
- エラー有り: Generator の出力を破棄し、内蔵の `build_report/build_failure.md` テンプレートでエラーページを `index.md` にレンダリングする

奥付は両方の分岐に付ける。失敗ページは表紙を置き換えるので、失敗時に読者が見る唯一のページになるため（失敗ページにだけ奥付を埋め込む理由は [奥付](20-build-information.md#奥付)）。表紙側で生成側（cover テンプレート）に build info を渡さないのは、末尾に何がどの順で並ぶか（**本文 → 奥付リンク → 警告リンク**）を Reconcile 一箇所で決めるため。

条件付きで現れる警告リンクを末尾に置くのは、**常設セクションの位置が警告の有無で動かない**ようにするため。奥付がページ末尾の表だった頃は「本の奥付」として最後が自然だったが、リンク節になった以上その理由は無い。

この分離により以下が成立する:

- Generator は「views を Markdown に変換する」純粋な責務に集中できる（エラー時の出力差し替えロジックを持たない）
- 下流の site / publish ステージは Reconcile の出力の単一視点を持てばよく、エラー時と正常時の分岐を知らなくてよい

「reconcile」の語を採った理由は[背景](../../90-appendix/20-design/75-meta-documentation/30-build-report.md#reconcile-の命名)。
