# システム設計ドキュメント

## エンティティ一覧



## リレーション一覧

| From | To | Cardinality | Description |
|------|-----|-------------|-------------|
| user | user_role | 1:N | ユーザーは複数のロールを持つ |
| role | user_role | 1:N | ロールは複数のユーザーに割り当てられる |
| user | order | 1:N | ユーザーは複数の注文を持つ |
| order | order_item | 1:N | 注文は複数の明細を持つ |
| product | order_item | 1:N | 商品は複数の注文明細に含まれる |
| product_category | product | 1:N | カテゴリは複数の商品を持つ |
| product_category | product_category | 1:N | カテゴリは子カテゴリを持つ（自己参照） |
