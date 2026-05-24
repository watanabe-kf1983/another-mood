# Template Specification

## External Design

### 背景: なぜ Undefined をエラーにしないか

Jinja2 は `undefined` クラスを差し替え可能で、厳密な `StrictUndefined`（全ての undefined アクセスでエラー）、チェイン可能な `ChainableUndefined`、デフォルトの `Undefined`（1 階層目はサイレント、チェインはエラー）の 3 段階を提供する。

本プロジェクトは `ChainableUndefined` を採用する。理由:

- 内蔵テンプレート・ユーザテンプレートのいずれも、スキーマから抽出される optional フィールド（`metadata`, `validation` 等）を頻繁に参照するため、ガードの記述負荷が重い
- デフォルトの `Undefined` は 1 階層目の typo も同様にサイレント失敗するため、チェインだけエラーにする中途半端な挙動になっている
- 厳密な typo 検出が必要になった時点で `StrictUndefined` への切り替えを検討する（その際は内蔵テンプレート側のガード追加が必要）

## Proposals

### C4 (paginate 自動判定) との関係

C4 では `paginate` 設定を見て `mood_view` が自動的に inline / 分割を判定する予定。現在の `inline` キーワードはその自動判定を上書きする明示指定として位置付けられる。C4 導入後も「常に inline を強制する escape hatch」として残すか、深い統合で吸収するかは C4 実装時に判断。

### テンプレート参照の拡張子明示化 (P2)

> **未実装** — Phase 11 タスク [P2](../../../tasks.md)

`{% mood_view %}` でテンプレートを参照する際、現状はテンプレート著者が拡張子を省いて書き、コード側が `.md` を補う形になっている:

```jinja2
{# 現状 #}
{% mood_view "by_role" with rows %}
{# 内部で "by_role.md" として解決 #}
```

これを **テンプレート著者がフルファイル名 (拡張子込み) を書く形** に変える:

```jinja2
{# 改修後 #}
{% mood_view "by_role.md" with rows %}
{% mood_view "diagram.mermaid" with data %}
```

#### 動機

- **複数 output_format への布石** — [output-format-spec.md](output-format-spec.md) で導入する output_format 別 Environment の選択は、テンプレート名の拡張子から format を引いて行う。拡張子が呼び出し側に明示されていることが前提となる。
- **コードリーディングの容易化** — `"by_role"` という識別子からテンプレートファイルを探すとき、拡張子の暗黙補完は読み手にとってのマジック。フルファイル名で書けば grep でそのまま辿れる。

#### 仕様

`{% mood_view EXPR with EXPR [inline] %}` の `EXPR` 第一引数は **拡張子込みのテンプレートファイル名** を返す式とする。`templates_dir` (および内蔵テンプレートディレクトリ) 配下のパスとして `get_template` に渡される。

コード側の `.md` 自動付与は廃止する。

#### 影響範囲

破壊的変更。以下を一斉に修正する:

- 実装: `template_engine` / `mood_view_processor` の 2 箇所で `.md` 付与を止める
- 内蔵テンプレート: `src/another_mood/resources/templates/` 配下
- `showcase/` 全 blueprint
- `dev-docs/` テンプレート
- `docs/reference/` の mood_view 説明・例示
- ユーザのテンプレート (利用者が showcase blueprint をコピーして始めている場合)
