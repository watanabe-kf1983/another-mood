# メタドキュメンテーション (appendix)

[メタドキュメンテーション](../../20-design/75-meta-documentation.md) の背景。

## View の Shape が必須な理由

本ツールは複合型 (object / object[]) を許容するため、カラムヘッダと
サンプル行だけでは結果形状が伝わらない (`tasks` カラムが scalar 文字列なのか、
`categories.tasks` 型の配列なのかが値だけでは断定できない)。

Shape セクションで各出力フィールドの型 + entity ref を明示する
ことで、template 著者 / MCP 経由の LLM / 人間の読者すべてに対して型情報が
programmatic に伝わる。SQL クライアントが (全カラムスカラ前提で) 型表示を
省略できるのと対照的。

Shape は Query Object の `derive` が生成する。定義から deterministic
に導出される型情報なので、置き場所は `__data` ではなく `__view_defs`:
entity def ページが「schema 定義 + 正規化後の型表」を見せるのと同じ、
「定義 + そこから決まる型」の構図になる。
