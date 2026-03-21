# JSON データモデル

## 定義

YAML DSL やテンプレートエンジンが操作する対象は「JSON データモデル」（object / array / string / number / boolean / null で構成されるツリー構造）である。JSON というシリアライズ形式とは無関係で、YAML から読み込んだデータに対しても同様に動作する。

Normalizer から Document Generator まで、全コンポーネントがこのデータモデル上で一貫して動作する。

なお、「JSON データモデル」という用語に対応する正式な仕様は存在しない（XML には XML Information Set という W3C 勧告があるが、JSON にはそれに相当するものがない）。CBOR の RFC 8949 が "the JSON data model" という表現を使用しており、本プロジェクトでもこれに倣う。

YAML のデータモデルは JSON データモデルのスーパーセット（日付型、整数/浮動小数の区別、アンカー等）だが、このアプリで扱うデータは JSON データモデルの範囲内に収まる。

## マージ戦略

複数のデータソース（YAML ファイル、Markdown ファイル等）から読み込まれた JSON データモデルのマージ戦略。

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

### 配列の結合

同じキーパスに配列が複数データソースに存在する場合、単純結合する:

```yaml
# file1.yaml
entities:
  - id: user

# file2.yaml
entities:
  - id: order
```

結果: `entities` は `[{id: user}, {id: order}]` になる。結合順はファイル名のアルファベット順に従う。

### 背景: 配列を単純結合とする理由

このツールはデータを RDBMS 的に扱う。配列（レコードセット）は順序に意味を持たない Iterable Collection であり、最終的な出力順は Generator が id 等でソートして決定する。したがって配列のマージは順序を気にせず単純結合でよい。

ファイル間で同一エンティティを分割して定義するケース（同じ id のオブジェクトが複数ファイルに存在）は、ファイル単位のスキーマ検証（`required` 等）によって自然に防がれる。各ファイルのエンティティはそれ単体でスキーマを満たす必要があるため、プロパティを別ファイルに分散させると検証エラーになる。

### 適用箇所

| コンポーネント | マージのタイミング | データソース |
|---|---|---|
| Normalizer | 正規化の後（制約検証のために内部マージ） | YAML ファイル + Markdown ファイル（prose スキーマ） |
| Composer | ビュー生成時 | 正規化済みファイル群 |
| Generator | テンプレート展開時 | ビューファイル群 |

### 未決事項

- **トップレベルスキーマが `type: array`（additionalProperties でない）の場合**: id を持たない配列のマージ・重複検出をどうするか未定
- **スキーマ名重複**: 複数スキーマファイルに同じトップレベルキーがあった場合の扱い（エラーとする想定だが未確定）
