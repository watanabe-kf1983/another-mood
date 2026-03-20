# order-management の ER図

## エンティティ一覧


### 注文

ユーザーが行った注文

| フィールド | 型 | 備考 |
|-----------|-----|------|
| id | string | PK |
| user_id | string | FK → user |
| total_amount | number |  |
| status | string |  |
| ordered_at | datetime |  |



### 注文明細

注文に含まれる商品明細

| フィールド | 型 | 備考 |
|-----------|-----|------|
| id | string | PK |
| order_id | string | FK → order |
| product_id | string | FK → product |
| quantity | number |  |
| unit_price | number |  |




---

[← トップに戻る](../_index.md)
