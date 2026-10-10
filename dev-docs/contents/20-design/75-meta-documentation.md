# メタドキュメンテーション

ユーザが書いたスキーマ定義とビュー定義を、ツールが内蔵のテンプレートで自動的に可視化する機能。

## External Design

- ビュー定義ページは Shape (各出力フィールドの型 + entity ref) を出し、Query Object の `derive` がそれを生成する。複合型を許容する本ツールでは、カラムヘッダとサンプル行だけでは結果形状が伝わらないため（[背景](../90-appendix/20-design/75-meta-documentation.md#view-の-shape-が必須な理由)）

## Proposals

### 内部オブジェクト診断の `--debug` 復活スイッチ

`__definition.*` やメタビュー自身のページは `where.not` で抑止しているが、カタログ自体をデバッグしたい場面 (built-in の挙動を疑うとき等) では見たくなりうる。その際は `mood build --debug` 相当のスイッチで `where.not` を外し、内部オブジェクトのページも出す案。常時は出さず opt-in にすることで、通常出力のノイズと debug 時の網羅性を両立する。スイッチの粒度 (build 全体か meta だけか) は実装時に確定。
