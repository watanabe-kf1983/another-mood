# CLI 仕様

## External Design

### 処理対象ディレクトリ

- CWD 配下のパスのみ許可。CWD 外のパス（`../other-repo/docs` 等）はエラーとする

## Proposals

### mood watch (--host)

```
mood watch <projectDir> [--host <addr>] [--port <port>]
```

`--host` は preview server の bind アドレス。デフォルト `127.0.0.1`（localhost のみ）。`0.0.0.0` 等を指定すると LAN 上の他端末から preview server に接続可能になる。preview server には認証がないため、信頼できるネットワーク内でのみ使うこと。

想定ユースケース: 要件定義 / 設計会議で 1 人がソースを更新、出席者全員が即座にブラウザでドキュメントを参照する collaborative authoring。同一 LAN 上のメンバーに対して `--host 0.0.0.0` で開く。
