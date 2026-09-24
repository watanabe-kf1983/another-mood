# Dev Docs (ドッグフーディング)

本プロジェクト自身の開発文書 (`dev-docs/`) を Another Mood で管理する、第一者コンテンツとしての設計。タスクカタログ・ロードマップ (L1–L3) に続き、外部ツールの機械出力を contents に取り込む実証を扱う。

## Proposals

### SBOM ドッグフーディング (L4)

タスク [L4](node:/tasks/L/tasks/L4)。自プロジェクトの部品表 (CycloneDX JSON) を dev-docs の contents に置き、ライセンス台帳とコンポーネント別ページを自動導出する。[Normalizer の JSON 入口](../50-normalizer/10-normalizer.md#背景-手書きは-yaml-推奨json-はワンショット機械出力の受け口)の「機械的ワンショット出力の contents 流用」の実証で、生成器の出力を **jq で最小限整形して** contents に置く。jq の仕事はスキーマ言語の制約に合わせること (封筒剥がし・名前の改名) に限り、読み替え (id の付与・逆引き・ライセンスの仕分け) は view の仕事とする。

#### 背景: 言語を緩めず、前段で整形する

当初は「生成器の出力をそのまま置き、データ側の変形はゼロ」を実証の主張とし、前提として名前規則の緩和 (`bom-ref` / `$schema` を宣言するため) と読み捨てキーの宣言 (封筒のため) をスキーマ言語側に足す案だった。検討の結果、両方とも取り下げた:

- 名前規則を緩めると、手で書く利用者 (正本の書き手) の規則まで緩む。緩和を外部取り込みを意図した利用者に絞る宣言 (部分木単位のスイッチ等) を突き詰めると、取り込み領域でスキーマを「契約」でなく「読み取りの射影」として扱うことになり、正本の整合性を守るという製品の核から外れる
- Excel の Power Query や Access のリンクテーブルと同じく、外部の形を本体の流儀に合わせるのは本体の外側の層の仕事。当面その層は作らず、jq で足りる
- 実測で足りた: SBOM 全体で識別子でないキーは `$schema` と `bom-ref` の 2 つのみ。下記の jq を通したデータは現行の言語でビルドが通る

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

- `component`: `from: components` → `select: [{ item: ref, as: id }, name, version, ...]`。配列 pattern の要素は `id` を持たないのでアンカーパスを持たないが、view の `select` で `id` を導出すれば要素が addressable になり、`file_per: [component.item]` で別ページに分割できる (roadmap view が `task.phase` を `id` にしているのと同じ形)
- `dependency_edges`: `from: dependencies` → `flatten: { of: dependsOn, as: dep }` → `join: { to: component, on: { left: dep, right: id }, flatten: {...} }`。辺リスト (ref → dep + 依存先の属性)
- `dependents`: `from: component` → `join: { to: dependency_edges, on: { left: id, right: dep } }`。逆引き (誰に使われているか)。ビューへの join で足りる
- `spdx_ledger`: `from: component` → `flatten: { of: licenses, as: lic }` → `where: { lic.license.id: { exists: true } }` → `grouped: { by: lic.license.id, as: components }`。SPDX id を持つものの台帳 (実測 8 種)
- `other_licenses`: 同じ flatten に `exists: false` の where。classifier 文字列と SPDX 式 (実測 6 件) を別表に出す

タスクの論点「`dependsOn` (文字列配列) を join で辿れるか」の結論: **join 側の変更は不要。** join は単一キー等値だが、トップレベル `flatten` が `string[]` を要素行に展開できるので、flatten → join の二段で辿れる。

**要判断: id の見栄え。** `ref` (元の `bom-ref`) は `name==version` 形なので、そのまま id にするとページパスが `component/PyJWT%3D%3D2.14.0.md` になる (IRI エスケープは正しく動くが URL が読めない)。venv では 1 パッケージ 1 版なので `name` を id にする手もあるが、`dependsOn` の参照は `ref` なので join 側は `ref` のまま残す必要がある (`select` で両方を持てば済む)。jq で `components` を `name` キーの map pattern に組み替える手もあるが、それは読み替えなので view 側で済ませる。

#### ページ

dev-docs index に「部品表」節を足す: コンポーネント一覧 (`component.item[]`)、コンポーネント別ページ (`component.item`: 版・ライセンス・purl・外部参照・依存先・依存元)、ライセンス台帳 (`spdx_ledger.item[]`)。web edition は分割、book edition はインライン (既存の二 edition 構成を踏襲)。

#### CI 組み込み

同期の担保は「生成物をコミットし、CI で再生成して diff が無いことを検査する」形にする (`make sbom` (生成 + jq) + `git diff --exit-code dev-docs/contents/sbom.json` を `make ci` に組み込む)。生成器を CI で走らせて出力をアーティファクト化するだけでは、dev-docs のビルド入力 (コミット済み sbom.json) が古いまま残る。

- uv.lock が変わる契機は二つ: `make upgrade-deps` (儀式) と Dependabot security updates。前者は `scripts/upgrade_deps.sh` に再生成を組み込む (「uv.lock 以外の変更を弾く」安全弁を `sbom.json` まで緩める)。後者は bot の PR に sbom.json が同乗しないので CI 検査が落ち、`make sbom` を足して merge する運用になる
- Python マトリクス両脚で同じ SBOM になる (上述) ので、検査はどちらの脚でも走らせてよい

#### 見つかったツール不足 (L3 と同型のフィードバック)

- `grouped.by` が存在しないキーを指すと、診断ではなく素の `KeyError` traceback で落ちる (プロトタイプで `lic.license.id` を where 無しで指定して遭遇)。`where` / `select` の欠損キー扱いと揃えた診断にすべき。別タスク (O) に切る
- 配列要素への x-ref (`items` の `x-ref`) は本タスクの前提どおり不要とするが、import blueprint 構想で参照整合性を謳うなら再浮上する

#### 採らない案

- **スキーマ言語を緩めて無加工で受ける** (名前規則の緩和・読み捨てキーの宣言): 上述の背景のとおり取り下げた
- **jq で読み替えまで行う** (map pattern への組み替え / ライセンスの正規化キー): 言語の制約に関係しない変形で、view の `select` (id の付与) と `where` の `exists` (ライセンスの仕分け) で足りることをプロトタイプで確認した。前段に持ち込むと、何が生成器の出力で何がこちらの解釈かが jq の中に埋もれる
- **requirements モード (`uv export` 経由)**: ライセンス・説明・外部参照が取れず (タスク備考どおり情報が痩せる)、`dependencies` グラフも出ない
- **`dependsOn` を `components` の属性に合流させて単一 entity にする**: テンプレートは単純になるが、CycloneDX の `components` / `dependencies` 分離を崩す。方言をそのまま受ける形を残す方が import blueprint の前身として意味がある
- **cyclonedx-bom を uvx で都度取得**: 上述 (版が固定されない)
