# Dev Docs (ドッグフーディング)

本プロジェクト自身の開発文書 (`dev-docs/`) を Another Mood で管理する、第一者コンテンツとしての設計。タスクカタログ・ロードマップ (L1–L3) に続き、外部ツールの機械出力を contents に取り込む実証を扱う。

## Proposals

### SBOM ドッグフーディング (L4)

タスク [L4](node:/tasks/L/tasks/L4)。自プロジェクトの部品表 (CycloneDX JSON) を dev-docs の contents に置き、ライセンス台帳とコンポーネント別ページを自動導出する。[Normalizer の JSON 入口](../50-normalizer/10-normalizer.md#背景-手書きは-yaml-推奨json-はワンショット機械出力の受け口)の「機械的ワンショット出力の contents 流用」の実証で、**生成器の出力をそのまま contents に置き、データ側の変形はゼロ**にする。封筒は schema.yaml で読み捨て、読み替え (id の付与・正規化・逆引き) はすべて view の仕事とする。

前提タスク (いずれも [schema-spec.md](../50-normalizer/20-schema-spec.md#proposals) の Proposals):

- [D12](node:/tasks/D/tasks/D12) 名前規則の緩和 — CycloneDX の `bom-ref` (ハイフン) と `$schema` を schema に宣言するため
- [D13](node:/tasks/D/tasks/D13) 読み捨てキーの宣言 — 封筒 (`$schema` / `bomFormat` / `specVersion` / `version` / `metadata`) を名指しで読み捨てるため。実測ではこれらは全て schema に宣言でき (ルート直下のスカラーとシングルトンは通る)、封筒が「うるさい」のは `metadata` の形を書き下す手間だけだった

#### 生成パイプライン

```
uv sync --no-dev --locked  (UV_PROJECT_ENVIRONMENT=.venv-sbom)
  → cyclonedx-py environment .venv-sbom --pyproject pyproject.toml --output-reproducible
  → dev-docs/contents/sbom.json  (そのまま)
```

- **対象環境はランタイム依存のみ** (`--no-dev` の使い捨て venv `.venv-sbom`、gitignore)。台帳が答える問いは「配布物が推移的に何を再頒布するか」であり、pytest / ruff 等の開発ツールを混ぜると問いがぼやける。開発環境の `.venv` をそのまま使う案は、環境が一つで済む代わりにこの問いに答えられないので採らない。実測: ランタイム 49 / 全体 62 コンポーネント
- **`--output-reproducible`** で timestamp / serialNumber を落とす。残る `metadata.tools` (生成器の版) は D13 で読み捨てる
- **`--pyproject` でルートコンポーネント** (another-mood 自身) を `metadata.component` に得る。その `dependsOn` (`dependencies` の `ref: root-component` 行) が直接依存の集合なので、`metadata` を部分宣言 (`component` だけ record、他は読み捨て) すれば「直接 / 推移的」の区別が view で導ける。要らなければ `metadata` ごと読み捨てる (要判断だが、どちらもデータ変形は不要)
- **cyclonedx-bom は dev dependency group に入れる** (`uv run cyclonedx-py`)。uvx の都度取得だと生成器の版が固定されず、出力形式のドリフトが CI の同期検査を偽陽性で落とす。dev group なら uv.lock に固定され、鮮度は既存の儀式 (`make upgrade-deps`) に乗る。ランタイム venv は `--no-dev` なので生成器自身は部品表に混ざらない
- **Linux でのみ生成する。** uv.lock の marker は Python 版には依存しない (3.12 / 3.13 で同一) が、プラットフォームには依存する (`colorama` / `pywin32` は win32 のみ)。CI (ubuntu) と devcontainer は Linux なので運用上は問題ないが、macOS / Windows のホストで生成すると diff が出る

#### スキーマ

封筒を名指しで読み捨て、CycloneDX の `components` / `dependencies` を配列 pattern のまま全キー宣言する。

```yaml
type: object
additionalProperties: false
properties:
  $schema:     { x-ignored: true }   # D12 (名前) + D13 (読み捨て)
  bomFormat:   { x-ignored: true }
  specVersion: { x-ignored: true }
  version:     { x-ignored: true }
  metadata:    { x-ignored: true }   # ルートコンポーネントが要るなら部分宣言
  components:                    # 配列 pattern。implicit id は無い (id は view で付ける)
    type: array
    items:
      properties:
        bom-ref: { type: string }  # D12
        name / version / type / description / purl: string
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

x-ref は張れない: `dependsOn` は配列 (x-ref は `type: string` 限定)、`bom-ref` は synthetic id ではない。参照整合性の検査は無しで、join (INNER 形) が宙に浮いた参照を黙って落とす。台帳の用途では許容する。

#### ビュー (使い捨てプロトタイプで検証済み)

- `component`: `from: components` → `select: [{ item: bom-ref, as: id }, name, version, ...]`。配列 pattern の要素は `id` を持たないのでアンカーパスを持たないが、view の `select` で `id` を導出すれば要素が addressable になり、`file_per: [component.item]` で別ページに分割できる (roadmap view が `task.phase` を `id` にしているのと同じ形)
- `dependency_edges`: `from: dependencies` → `flatten: { of: dependsOn, as: dep }` → `join: { to: component, on: { left: dep, right: id }, flatten: {...} }`。辺リスト (ref → dep + 依存先の属性)
- `dependents`: `from: component` → `join: { to: dependency_edges, on: { left: id, right: dep } }`。逆引き (誰に使われているか)。ビューへの join で足りる
- `spdx_ledger`: `from: component` → `flatten: { of: licenses, as: lic }` → `where: { lic.license.id: { exists: true } }` → `grouped: { by: lic.license.id, as: components }`。SPDX id を持つものの台帳 (実測 8 種)
- `other_licenses`: 同じ flatten に `exists: false` の where。classifier 文字列と SPDX 式 (実測 6 件) を別表に出す

タスクの論点「`dependsOn` (文字列配列) を join で辿れるか」の結論: **join 側の変更は不要。** join は単一キー等値だが、トップレベル `flatten` が `string[]` を要素行に展開できるので、flatten → join の二段で辿れる。

**要判断: id の見栄え。** `bom-ref` は `name==version` 形なので、そのまま id にするとページパスが `component/PyJWT%3D%3D2.14.0.md` になる (IRI エスケープは正しく動くが URL が読めない)。venv では 1 パッケージ 1 版なので `name` を id にする手もあるが、`dependsOn` の参照は bom-ref なので join 側は bom-ref のまま残す必要がある (`select` で両方を持てば済む)。

#### ページ

dev-docs index に「部品表」節を足す: コンポーネント一覧 (`component.item[]`)、コンポーネント別ページ (`component.item`: 版・ライセンス・purl・外部参照・依存先・依存元)、ライセンス台帳 (`spdx_ledger.item[]`)。web edition は分割、book edition はインライン (既存の二 edition 構成を踏襲)。

#### CI 組み込み

同期の担保は「生成物をコミットし、CI で再生成して diff が無いことを検査する」形にする (`make sbom` + `git diff --exit-code dev-docs/contents/sbom.json` を `make ci` に組み込む)。生成器を CI で走らせて出力をアーティファクト化するだけでは、dev-docs のビルド入力 (コミット済み sbom.json) が古いまま残る。

- uv.lock が変わる契機は二つ: `make upgrade-deps` (儀式) と Dependabot security updates。前者は `scripts/upgrade_deps.sh` に再生成を組み込む (「uv.lock 以外の変更を弾く」安全弁を `sbom.json` まで緩める)。後者は bot の PR に sbom.json が同乗しないので CI 検査が落ち、`make sbom` を足して merge する運用になる
- Python マトリクス両脚で同じ SBOM になる (上述) ので、検査はどちらの脚でも走らせてよい

#### 見つかったツール不足 (L3 と同型のフィードバック)

- property 名の識別子制約 → [D12](node:/tasks/D/tasks/D12)。封筒の書き下しの手間 → [D13](node:/tasks/D/tasks/D13)
- `grouped.by` が存在しないキーを指すと、診断ではなく素の `KeyError` traceback で落ちる (プロトタイプで `lic.license.id` を where 無しで指定して遭遇)。`where` / `select` の欠損キー扱いと揃えた診断にすべき。別タスク (O) に切る
- 配列要素への x-ref (`items` の `x-ref`) は本タスクの前提どおり不要とするが、import blueprint 構想で参照整合性を謳うなら再浮上する

#### 採らない案

- **jq で前処理する** (封筒剥がし / `bom-ref` の改名 / map pattern への組み替え / ライセンスの正規化キー): いずれも「機械出力をそのまま受ける」という実証の主張を弱める。封筒は D13、名前は D12 で schema 側に吸収し、id の付与は view の `select`、ライセンスの仕分けは `where` の `exists` で足りることをプロトタイプで確認した
- **requirements モード (`uv export` 経由)**: ライセンス・説明・外部参照が取れず (タスク備考どおり情報が痩せる)、`dependencies` グラフも出ない
- **`dependsOn` を `components` の属性に合流させて単一 entity にする**: テンプレートは単純になるが、CycloneDX の `components` / `dependencies` 分離を崩す。方言をそのまま受ける形を残す方が import blueprint の前身として意味がある
- **cyclonedx-bom を uvx で都度取得**: 上述 (版が固定されない)
