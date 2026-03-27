# エラー伝播

## 概要

各コンポーネントで発生したエラーを、パイプラインの正常なデータフローに載せてブラウザまで届ける仕組み。

dev モードではユーザはブラウザを見ており、ターミナルの stderr を見ていない可能性が高い。エラーが発生したことをユーザに気づかせるには、エラー情報を通常のデータと同じ経路で最下流まで流し、最終的に HTML としてレンダリングする必要がある。

## エラーの表現

エラーは `__errors` キーを持つ YAML ファイルとして表現する（`__` プレフィックスはシステム内部予約。[json-data-model.md](json-data-model.md) 参照）。

```yaml
__errors:
  - source: "contents/entities.yaml"
    message: "Unknown field 'stauts' in entity"
    traceback: |
      Traceback (most recent call last):
        File ...
      ValidationError: Unknown field 'stauts' in entity
```

| フィールド | 説明 |
|---|---|
| `source` | エラー原因のファイルパス |
| `message` | エラーメッセージ（Python 例外のメッセージ） |
| `traceback` | Python トレースバック全体 |

エラー情報は Python 例外をそのまま構造化したもの。ユーザ向けのメッセージもカスタム例外のメッセージとして表現する。

## エラー時の出力

コンポーネントでエラーが発生した場合、そのコンポーネントの出力ディレクトリには **`__errors` ファイルのみ** が置かれる。正常に処理できたファイルも含めて、正常出力はすべて除去する。

エラーが発生したことをユーザに確実に気づかせるため、中途半端に正常らしき出力を下流に流さない。

## パススルー規約

各コンポーネントは処理開始時に入力ディレクトリの `__errors` ファイルを検査する。`__errors` ファイルが存在する場合、自身の処理をスキップし、`__errors` ファイルをそのまま出力ディレクトリにコピーする。

これにより、上流で発生したエラーはパイプライン最下流の Generator まで到達する。

## 各コンポーネントの振る舞い

| コンポーネント | エラー出力形式 | パススルー |
|---|---|---|
| Normalizer | `__errors` YAML | 入力に `__errors` があればパススルー |
| Composer | `__errors` YAML | 入力に `__errors` があればパススルー |
| Generator | `__errors` を内蔵テンプレートで **Markdown** にレンダリング | 入力に `__errors` があれば Markdown に変換 |
| Renderer (Hugo) | 対象外（stderr にそのまま出力） | — |

## 実装方針: ミドルウェア

エラーのキャッチとパススルーは全コンポーネント共通の処理であり、各コンポーネントの内部には書かない。AtomicDirWriter の内側でコンポーネント関数をラップするミドルウェアとして実装する。

```
Stage → AtomicDirWriter → ErrorMiddleware → Component
```

- **ErrorMiddleware** が上流 `__errors` の検査・パススルーとコンポーネント例外のキャッチ・YAML 変換を担当
- **AtomicDirWriter** はエラー YAML の出力もアトミックに書き込む
- **Watcher** の既存の `except Exception`（stderr 出力）は、AtomicDirWriter やミドルウェア自体の想定外エラーのフォールバックとして残る

### 背景: AtomicDirWriter の外側ではなく内側に置く理由

AtomicDirWriter のエラー（ロック取得失敗、ディスク書き込み失敗等）は「ファイルを安全に書く仕組み自体の障害」であり、`__errors` YAML を書こうとしても同じ理由で書けない可能性が高い。AtomicDirWriter を信頼して使う以上、その障害時に AtomicDirWriter を迂回して書くのは矛盾する。これらのエラーは Watcher の既存のフォールバック（stderr 出力）に任せる。
