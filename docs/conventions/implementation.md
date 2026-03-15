# 実装工程の規約

## コードスタイル

- **関数型スタイルを優先**: `let` + `for` ループより `map/filter/reduce` を使う
- **命名はモジュール名に合わせる**: `source` モジュールなら `isSourceFile`, `buildSource`
- **関数の並び順（Newspaper style）**: 公開API を先頭に、ヘルパー関数を後に配置。ヘルパーはパイプラインの順序に沿って配置

## テスト

- **対象**: `src/core/` 配下のビジネスロジック（`src/cli.ts`, `src/commands/` は対象外）
- **カバレッジ目標**: 85%以上
- **アプローチ**: テストファースト（TDD）
- **フィクスチャ**: ファイルベース、モジュール隣接型（`source.fixtures/`）。期待値はテストコード内に記述

## タスクの進め方

1. **example-project に入出力例を作成** - 具体的な入力と期待出力で仕様を合意
2. **単体テストを記述** - 期待する振る舞いをテストコードで表現
3. **実装してテストをパス**
4. **example-project で動作確認**
5. **`npm run ci`** を実行してからコミット（format, lint, secretlint, build, test:coverage）
6. 完了したらチェックを入れてプルリクを作成
