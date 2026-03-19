# Composer

## 処理フロー

1. `normalizedSchemaDir`、`normalizedContentsDir`、`normalizedQueriesDir` の *.yaml 読み込み
2. normalizedQueriesDir のクエリを評価（normalized データに対して from/join/where/group_by/select/sort を適用）
   - join はデフォルト LEFT JOIN
3. `viewsDir` に *.yaml として書き出し

## 背景: YAML DSL の採用理由

テンプレートエンジン（LiquidJS / Jinja2）でも JSONata でもなく、YAML DSL を選択した理由:

- **クエリ自体が構造化データ**: このツール自身で管理・検証・可視化できる（dog fooding）
- **AI が MCP 経由で編集可能**: JSONPath + JSON Patch でクエリ定義を操作できる
- **Access の Query Design View に相当する可視化**: クエリ定義を Mermaid 等で図示できる

### テンプレートエンジンによるデータ変換の限界

旧設計では LiquidJS / Jinja2 テンプレートで source データを整形していた:

```yaml
# 旧: reports/erd.yaml.liquid（テンプレートエンジンでデータ変換）
erd:
  {% assign categories = source.entities | map: "category" | uniq %}
  {% for cat in categories %}
  - key: "{{ cat }}"
    title: "{{ cat }} の ER図"
    entity:
      {% assign ents = source.entities | where: "category", cat %}
      ...
  {% endfor %}
```

これは本質的に SQL の SELECT / WHERE / DISTINCT / GROUP BY に相当する操作を、テキスト生成エンジンで行っている。問題点:

1. **データ→テキスト→データのラウンドトリップ**: source（オブジェクト）→ Liquid でテキスト生成 → YAML パース → オブジェクト。不要な変換が2回入る
2. **YAML エスケープ問題**: テキストとして YAML を生成するため、ノルウェー問題（`NO` が boolean 扱い）等のエスケープ問題が発生する
3. **型の劣化**: テキスト経由で整数・浮動小数の区別等が失われる可能性

この課題が Composer（YAML DSL によるデータ変換）を導入した動機である。

## Technical Stack

次期版で新規実装。現行 TypeScript 実装には対応するコンポーネントがない。
