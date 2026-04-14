# 本プロジェクトのドキュメントについて

本プロジェクトはドキュメント生成ツール another-mood を用いて文書を管理しています。ドキュメントを読む場合・書く場合、それぞれ以下に示す手順に従ってください。

## ドキュメントを読むには

以下のコマンドでドキュメントをビルドする（Python CLI ツール。動かない場合は下記参照）:

```bash
mood build docs-src
```

ビルドされたドキュメントは `.another-mood/docs-src/output/` に出力される。

起点: [.another-mood/docs-src/output/prose/index.md](../.another-mood/docs-src/output/prose/index.md)

コマンドが動かない場合は、[uv](https://docs.astral.sh/uv/) をインストールし `uv sync` を実行する。

## ドキュメントを編集するには

ソース (`docs-src/contents/`) を編集する場合、`mood dev` を使うとファイル変更を検知して自動でリビルドされる:

```bash
mood dev docs-src
```

> **このプロジェクトの開発時**: another-mood 自身の Python コードを変更する場合、`mood dev` は古いコードで動き続ける。そのため `mood build docs-src` をつど実行する。
