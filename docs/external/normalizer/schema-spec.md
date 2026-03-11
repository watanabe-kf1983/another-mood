# Schema Specification

スキーマ定義の仕様。データ構造と参照制約を定義する。

## 基本方針

OpenAPI/JSON Schema 互換 + `x-ref` 拡張で外部キー参照を表現する。

## スキーマ定義の例

```yaml
components:
  schemas:
    Entity:
      type: object
      required: [id, name]
      properties:
        id:
          type: string
        name:
          type: string
        description:
          type: string

    DataStore:
      type: object
      required: [id, entity_ref]
      properties:
        id:
          type: string
        entity_ref:
          type: string
          x-ref:
            target: Entity
            field: id
```

## x-ref 拡張

`x-ref` は外部キー参照を表現するための独自拡張：

```yaml
x-ref:
  target: Entity    # 参照先のスキーマ名
  field: id         # 参照先のフィールド名
```

- OpenAPI/JSON Schema の `x-` プレフィックス規約に従う
- 既存ツール（swagger-codegen 等）は `x-` 拡張を無視するため、互換性を維持

## 設計判断

### OpenAPI/JSON Schema ベースを採用した理由

- 業界標準、ドキュメント豊富
- 各言語への型生成ツールが既存（Python/Pydantic, TypeScript/Zod 等）
- `x-` プレフィックスで独自拡張可能（既存ツールは無視するだけ）

### データストア方針

- 最初は参照チェックのみ（インメモリで十分）
- クエリは JSONPath で対応
- 複雑な JOIN・集計が必要になったら SQLite 導入を検討
- GraphQL は実装コストが高いため見送り
