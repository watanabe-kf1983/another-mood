# 本プロジェクトのドキュメントについて

本プロジェクトはドキュメント生成ツール reqs-builder を用いて文書を管理しています。ドキュメントを読む場合・書く場合、それぞれ以下に示す手順に従ってください。

## ドキュメントを読むには

以下のコマンドでドキュメントをビルドする（Python CLI ツール。動かない場合は下記参照）:

```bash
reqs build docs-src
```

ビルドされたドキュメントは `.reqs-builder/docs-src/output/` に出力される。

起点: [.reqs-builder/docs-src/output/index.md](../.reqs-builder/docs-src/output/index.md)

コマンドが動かない場合は、[uv](https://docs.astral.sh/uv/) をインストールし `uv sync` を実行する。

## ドキュメントを編集するには

ソース (`docs-src/contents/`) を編集する場合、`reqs dev` を使うとファイル変更を検知して自動でリビルドされる:

```bash
reqs dev docs-src
```

> **このプロジェクトの開発時**: reqs-builder 自身の Python コードを変更する場合、`reqs dev` は古いコードで動き続ける。そのため `reqs build docs-src` をつど実行する。
