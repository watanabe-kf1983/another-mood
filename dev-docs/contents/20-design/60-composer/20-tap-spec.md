# Tap Specification

compose 結果を機械可読な形で外部に取り出す経路（`mood tap` + MCP `tap`）の設計。（tap = パイプラインの途中に口をあけ、混ざったものを流れを止めずに抜き出す）。挙動の正本は docs/reference/cli.md と docs/mcp.md。

## External Design

tap は成果物（1 本の JSON ドキュメント）を作るだけで、照会・絞り込みの口を持たない。以下は、その背後にある判断。

- ソースを直接読ませず tap を置くのは、ソースが著者の書きやすい形であって照会しやすい形ではないため（[背景](../../90-appendix/20-design/60-composer/20-tap-spec.md#ソースを直読みさせない理由)）
- 照会は利用者の道具（jq 等）に委ね、jq 引数も部分指定も持たない（[背景](../../90-appendix/20-design/60-composer/20-tap-spec.md#jq-引数を持たせない理由)）。MCP は payload を返り値に載せない。600KB 級の木を tool result に載せるとエージェントのコンテキストを圧迫する
- 出力は JSON のみ（[背景](../../90-appendix/20-design/60-composer/20-tap-spec.md#json-のみにした理由)）
