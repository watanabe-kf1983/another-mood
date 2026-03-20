# YAML ディレクトリ読み込み

コンポーネント共通の入力読み込みロジック。

## 処理フロー

1. 入力ディレクトリから `*.yaml` / `*.yml` ファイルを列挙
2. ファイル名のアルファベット順にソート
3. 各ファイルを YAML としてパースし、トップレベルがオブジェクトであることを検証
4. 全ファイルを deep merge して単一オブジェクトとして返す

## マージ戦略

### オブジェクトの再帰マージ

ネストされたオブジェクトは再帰的にマージされる:

```yaml
# file1.yaml
config:
  database:
    host: localhost

# file2.yaml
config:
  database:
    port: 5432
```

結果: `config.database` は `{host: localhost, port: 5432}` になる。

### スカラー値の衝突

同じキーパスにスカラー値がある場合、アルファベット順で後のファイルが勝つ:

```yaml
# file1.yaml
config:
  database:
    host: localhost

# file2.yaml（file1 より後）
config:
  database:
    host: production-server
```

結果: `config.database.host` は `production-server` になる。

### 配列の衝突は禁止

同じキーパスに非空の配列が複数ファイルに存在する場合はエラーとする:

```yaml
# file1.yaml
entities:
  - id: user

# file2.yaml
entities:       # エラー: 配列のマージは許可しない
  - id: order
```

空配列は衝突とみなさない（片方が空なら非空側をそのまま採用）。

## 背景: 配列マージを禁止する理由

配列のマージには append・replace・要素単位マージ等の複数の解釈がありえる。どの戦略を採用しても暗黙の挙動となり、意図しない結果を生みやすい。配列データは1つのファイルにまとめることを強制し、曖昧さを排除する。

## 適用箇所

このロジックは各コンポーネントが入力ディレクトリを読み込む際に共通で使用する。Normalizer（schema / contents / queries の各ステージ）では必須。Composer・Generator での必要性はそれぞれの入力形態による。
