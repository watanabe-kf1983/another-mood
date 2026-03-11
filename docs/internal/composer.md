# Composer

## 処理フロー

1. output/model/normalized/*.yaml 読み込み
2. model/queries/*.yaml 読み込み（YAML DSL）
3. YAML DSL を評価（normalized データに対して from/join/where/group_by/select/sort を適用）
   - join はデフォルト LEFT JOIN
4. output/model/views/*.yaml に書き出し

## Technical Stack

次期版で新規実装。現行 TypeScript 実装には対応するコンポーネントがない。
