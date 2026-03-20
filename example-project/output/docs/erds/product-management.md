# product-management の ER図

## エンティティ一覧


### 商品

販売する商品

| フィールド | 型 | 備考 |
|-----------|-----|------|
| id | string | PK |
| name | string |  |
| price | number |  |
| stock | number |  |
| category_id | string | FK → product_category |



### 商品カテゴリ

商品の分類カテゴリ

| フィールド | 型 | 備考 |
|-----------|-----|------|
| id | string | PK |
| name | string |  |
| parent_id | string | FK → product_category |




---

[← トップに戻る](../_index.md)
