# SBOM

外部ツールの機械出力 (CycloneDX JSON) を contents に取り込む showcase の設計。

## Proposals

### SBOM showcase (R6)

タスク [R6](node:/tasks/R/tasks/R6)。another-mood 自身の部品表 (CycloneDX JSON) をサンプルデータとする showcase を新しく立て、ライセンス台帳とコンポーネント別ページを view で導出する。[Normalizer の JSON 入口](../50-normalizer/10-normalizer.md#背景-手書きは-yaml-推奨json-はワンショット機械出力の受け口)の「機械的ワンショット出力の contents 流用」を利用者に見せる手本で、well-known 方言向け import blueprint 構想 (筆頭候補 CycloneDX) の前身を兼ねる。生成器の出力を **jq で最小限整形して** contents に置く。jq の仕事はスキーマ言語の制約に合わせること (封筒剥がし・名前の改名) に限り、読み替え (id の付与・逆引き・ライセンスの仕分け) は view の仕事とする。

showcase の言語は starter / music と同じく英語。

#### 背景: 言語を緩めず、前段で整形する

当初は「生成器の出力をそのまま置き、データ側の変形はゼロ」を実証の主張とし、前提として名前規則の緩和 (`bom-ref` / `$schema` を宣言するため) と読み捨てキーの宣言 (封筒のため) をスキーマ言語側に足す案だった。検討の結果、両方とも取り下げた:

- 名前規則を緩めると、手で書く利用者 (正本の書き手) の規則まで緩む。緩和を外部取り込みを意図した利用者に絞る宣言 (部分木単位のスイッチ等) を突き詰めると、取り込み領域でスキーマを「契約」でなく「読み取りの射影」として扱うことになり、正本の整合性を守るという製品の核から外れる
- Excel の Power Query や Access のリンクテーブルと同じく、外部の形を本体の流儀に合わせるのは本体の外側の層の仕事。当面その層は作らず、jq で足りる
- 実測で足りた: SBOM 全体で識別子でないキーは `$schema` と `bom-ref` の 2 つのみ。封筒を剥がし `bom-ref` を `ref` に改名した jq の出力は、現行の言語でビルドが通る

#### データ: スナップショットと生成手順

- **データはある時点の断面。** showcase のサンプルであって台帳の正本ではないので、another-mood の依存の変化には追従させない。CI での再生成・同期検査は置かない。取り直したくなったら生成手順を手で再実行する
- **生成手順は contents に同梱する。** `cyclonedx-py` の実行と jq を prose (Markdown) に書き、showcase のページとしても出す。外部 JSON をどう整えて受けるかがこの showcase の見せたいものなので、手順はデータの横に置く
- **対象はランタイム依存のみの環境** (`uv sync --no-dev` の使い捨て venv)。台帳の問いを「配布物と一緒に何が入るか」に絞るため、pytest / ruff 等の開発ツールは混ぜない。`--output-reproducible` で timestamp / serialNumber を落とし、`--pyproject` でルートコンポーネント (another-mood 自身) を得る
- **生成器は uvx で叩く** (`cyclonedx-bom` パッケージ。uv 本体に sbom コマンドは無い)。手順を読んだ利用者が自分のプロジェクトでそのまま再現できる形を優先する

#### スキーマ

jq の出力をそのまま受ける。`components` / `dependencies` は配列 pattern のまま全キー宣言する。

```yaml
type: object
additionalProperties: false
properties:
  root_component:                # シングルトン (record)
    properties: { ref, name, version: string }
  components:                    # 配列 pattern。implicit id は無い (id は view で付ける)
    type: array
    items:
      properties:
        ref / name / version / type / description / purl: string
        licenses[]: { license: { id, name, acknowledgement }, expression, acknowledgement }
        externalReferences[]: { type, url, comment }
        properties[]: { name, value }
  dependencies:
    type: array
    items:
      properties:
        ref: { type: string }
        dependsOn: { type: array, items: { type: string } }
```

ライセンスは SPDX id / classifier 文字列 (`name`) / SPDX 式 (`expression`) の 3 形が混在する (実測 63 件中 name 3 件・expression 3 件) が、全プロパティを任意にした 1 つの形で受かる。

x-ref は張れない: `dependsOn` は配列 (x-ref は `type: string` 限定)、`ref` は synthetic id ではない。参照整合性の検査は無しで、join (INNER 形) が宙に浮いた参照を黙って落とす。台帳の用途では許容する。

#### ビュー (使い捨てプロトタイプで検証済み)

- `component`: `from: components` → `select: [{ item: name, as: id }, ref, version, ...]`。配列 pattern の要素は `id` を持たないのでアンカーパスを持たないが、view の `select` で `id` を導出すれば要素が addressable になり、`file_per: [component.item]` で別ページに分割できる (roadmap view が `task.phase` を `id` にしているのと同じ形)
- `dependency_edges`: `from: dependencies` → `flatten: { of: dependsOn, as: dep }` → `join: { to: component, on: { left: dep, right: ref }, flatten: {...} }`。辺リスト (ref → dep + 依存先の属性)
- `dependents`: `from: component` → `join: { to: dependency_edges, on: { left: ref, right: dep } }`。逆引き (誰に使われているか)。ビューへの join で足りる
- `spdx_ledger`: `from: component` → `flatten: { of: licenses, as: lic }` → `where: { lic.license.id: { exists: true } }` → `grouped: { by: lic.license.id, as: components }`。SPDX id を持つものの台帳 (実測 8 種)
- `other_licenses`: 同じ flatten に `exists: false` の where。classifier 文字列と SPDX 式 (実測 6 件) を別表に出す

`dependsOn` (文字列配列) を join で辿れるか: **join 側の変更は不要。** join は単一キー等値だが、トップレベル `flatten` が `string[]` を要素行に展開できるので、flatten → join の二段で辿れる。

**id はパッケージ名。** `ref` (元の `bom-ref`) は `name==version` 形なので、そのまま id にするとページパスが `component/PyJWT%3D%3D2.14.0.md` になり URL が読めない。1 つの環境には 1 パッケージ 1 版しか入らないので `name` で一意になる。`dependsOn` の参照は `ref` なので、`select` で両方を持ち、join は `ref` で張る。

**直接依存と推移的依存を区別して見せる。** `dependencies` のうちルートコンポーネントの行の `dependsOn` が直接依存の集合なので、view で導く (この形はプロトタイプ未検証)。

#### ページ

- 生成手順 (contents の prose)
- コンポーネント一覧 (`component.item[]`)。直接 / 推移的の別を添える
- コンポーネント別ページ (`component.item`): 版・ライセンス・purl・外部参照・依存先・依存元
- ライセンス台帳 (`spdx_ledger.item[]` と `other_licenses`)

#### 見つかったツール不足

- `grouped.by` が存在しないキーを指すと、診断ではなく素の `KeyError` traceback で落ちる (プロトタイプで `lic.license.id` を where 無しで指定して遭遇)。`where` / `select` の欠損キー扱いと揃えた診断にすべき。別タスク (O) に切る
- 配列要素への x-ref (`items` の `x-ref`) は本タスクでは不要とするが、import blueprint 構想で参照整合性を謳うなら再浮上する

#### 採らない案

- **スキーマ言語を緩めて無加工で受ける** (名前規則の緩和・読み捨てキーの宣言): 上述の背景のとおり取り下げた
- **jq で読み替えまで行う** (map pattern への組み替え / ライセンスの正規化キー): 言語の制約に関係しない変形で、view の `select` (id の付与) と `where` の `exists` (ライセンスの仕分け) で足りることをプロトタイプで確認した。前段に持ち込むと、何が生成器の出力で何がこちらの解釈かが jq の中に埋もれる
- **requirements モード (`uv export` 経由)**: ライセンス・説明・外部参照が取れず情報が痩せ、`dependencies` グラフも出ない
- **`dependsOn` を `components` の属性に合流させて単一 entity にする**: テンプレートは単純になるが、CycloneDX の `components` / `dependencies` 分離を崩す。方言をそのまま受ける形を残す方が import blueprint の前身として意味がある
