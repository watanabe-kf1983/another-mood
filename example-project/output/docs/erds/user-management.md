# user-management の ER図

## エンティティ一覧


### ユーザー

システムを利用するユーザー

| フィールド | 型 | 備考 |
|-----------|-----|------|
| id | string | PK |
| email | string |  |
| name | string |  |
| created_at | datetime |  |



### ロール

ユーザーに割り当てる権限ロール

| フィールド | 型 | 備考 |
|-----------|-----|------|
| id | string | PK |
| name | string |  |
| permissions | string[] |  |



### ユーザーロール

ユーザーとロールの関連

| フィールド | 型 | 備考 |
|-----------|-----|------|
| user_id | string | PKFK → user |
| role_id | string | PKFK → role |




---

[← トップに戻る](../_index.md)
