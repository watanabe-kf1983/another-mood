# Style Guide

このプロジェクトのドキュメント・コード内での表記規約。

## ツール名の表記

| レイヤー | 表記 |
|---|---|
| 散文（README / docs / dev-docs / docstring / --help / コミットメッセージ等） | `Another Mood` |
| パス・ディレクトリ・URL 言及 | `another-mood` |
| PyPI / GitHub リポジトリ / プロジェクトルート | `another-mood` |
| Python パッケージ・モジュール | `another_mood` |
| CLI コマンド | `mood` |

体言をハイフンで繋ぐ綴り（`another-mood`）は英語として不自然なので、散文では title case の `Another Mood` を使う。技術的識別子（URL・パス・パッケージ名）は GitHub / PyPI / 言語制約のため `another-mood` のまま。判断基準は「**ファイル形式ではなく用法**」: コード内の docstring や `--help` 出力も人間が英文として読む箇所は散文扱い。

## 自己定義（tagline / description）の書き方

ツールの自己定義には2階層あり、混ぜずに分けて書く:

- **Means（普遍・固定）**: ソースベース DB のプロセッサ — 実装の本質
- **Effect（現に提供している価値）**: 現時点で実際に届けているもの

書き分けのルール:

- pyproject.toml description / `mood --help` / README 冒頭などの tagline は **Means + 現 Effect** の形で書く
  - 例: `A processor of source-based databases, keeping related documents in sync.`
- Effect 側は**未来の拡張を匂わせない**（"and other ..." 等を入れない）。誠実さを優先
- 一方で Vision を Effect に固定して書くのは避ける（"documentation build tool" は Means の解釈を狭めるので NG）
- product.md の Vision は Effect レイヤーの抽象化として別管理。tagline と Vision の整合は時間とともにずれてよい
