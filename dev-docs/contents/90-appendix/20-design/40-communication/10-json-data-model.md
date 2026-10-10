# JSON データモデル (appendix)

[JSON データモデル](../../../20-design/40-communication/10-json-data-model.md) の背景。

## YAML を 1.2 とする理由

本文の系統 (1) ユーザ入力と (2) 内蔵スキーマリソースに適用:

- ブール値が `true`/`false` のみに限定される。1.1 で問題になる `yes`/`no`/`on`/`off` の意図せぬブール化（通称 Norway 問題: `country: NO` がブール `False` になる）を回避できる。
- 全ての JSON ドキュメントが valid YAML 1.2 ドキュメントとなる。(1) で JSON 入力を受けるのに追加の parser を要さない。
- ruamel.yaml の既定が 1.2。`version` 指定が不要。

## 中間表現を JSON とする理由

本文の系統 (3) ステージ間中間表現に適用:

ビルド時間のうち ruamel.yaml が支配的だったため。差し替え前の `mood build dev-docs` は 2.67 s、うち中間表現の read/write が cProfile 下で 3.3 s（総 6.07 s の 54%）を占めていた。JSON へ差し替えた後は 1.79 s。tmp 配下は外部契約ではないので、変更は内部に閉じる。

PyYAML の CSafeLoader/Dumper (libyaml) なら YAML のまま 15 倍速くなるが採らない。PyYAML は YAML 1.1 なので、上記の 1.2 を選んだ理由がそのまま失われる。JSON はその曖昧さが構造的に無い。pickle / marshal も計測したが load はほぼ同速（差は 1 ms 未満）で、可読性を失うだけ。

代償は複数行文字列の可読性。YAML の literal block scalar に相当する規約が JSON に無いため、`\n` エスケープの 1 行になり post-mortem 時に読みにくい。`indent=2` と `ensure_ascii=False` で構造と非 ASCII 文字の可読性は保つ。
