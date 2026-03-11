# API Design (Future)

MCP サーバ / CLI の API 設計。Phase 3 で実装予定。

## 提供形式

同一機能を2つのインターフェースで提供：

- **CLI**: 人間向け、シェルスクリプト連携用
- **MCP サーバ**: AI エージェント向け（ツール定義が構造化されて提供される）

## なぜ両方必要か

- CLI のみだと AI は使い方を README や --help から推測する必要がある
- MCP はツールの引数・型・説明が構造化されており、AI が迷わず使える
- 人間は CLI の方が使いやすい場面も多い

## API 設計方針

**JSONPath + Patch 方式**を採用し、スキーマに依存しない汎用 CRUD を提供：

- **Read**: JSONPath クエリ
- **Create/Update/Delete**: JSON Patch (RFC 6902) の操作 + JSONPath によるパス指定

### Read（クエリ）

```typescript
function query(jsonpath: string): unknown[];
// 例: query("$.screens[?@.entity_ref=='User']")
```

### Create/Update/Delete（ミューテーション）

JSON Patch の `op` と JSONPath の `path` を組み合わせた方式：

```typescript
interface Operation {
  op: 'add' | 'replace' | 'remove';
  path: string;  // JSONPath
  value?: unknown;  // remove 時は不要
}

function mutate(operations: Operation[]): MutateResult;

// 例:
// 追加
{ op: "add", path: "$.screens", value: { id: "customer-list", name: "お客様一覧", entity_ref: "User" } }

// 更新
{ op: "replace", path: "$.screens[?@.id=='customer-list'].name", value: "顧客一覧画面" }

// 削除
{ op: "remove", path: "$.screens[?@.id=='customer-list']" }
```

### 検証

```typescript
interface ValidationError {
  path: string;
  message: string;
  code: string;
}

function validate(): ValidationError[];
// mutate() は内部で自動的に検証を実行し、エラー時はロールバック
```

## 設計判断

### CUD を API 経由にする理由

- 検証が必ず実行される（忘れない）
- LLM の認知負荷を下げる（YAML 構造を理解する必要がない）
- 1回の呼び出しで完結（編集→検証→エラー修正ループが不要）

### YAML 直接編集も許容

- 人間や LLM が直接編集しても構わない
- その場合は `validate` コマンド/API で事後検証

### JSONPath + Patch 方式を採用した理由

- Read で使う JSONPath をそのまま CUD にも流用できる
- スキーマから個別の CRUD API を生成する必要がない（汎用）
- JSON Patch (RFC 6902) の操作セマンティクスを借用し学習コストを下げる
- GraphQL は実装コストが高いため見送り（将来必要になれば検討）
