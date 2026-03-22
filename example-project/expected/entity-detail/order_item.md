# 注文明細

注文に含まれる商品明細

| フィールド | 型 | 備考 |
|-----------|-----|------|
| id | string | PK |
| order_id | string | FK → order |
| product_id | string | FK → product |
| quantity | number |  |
| unit_price | number |  |

