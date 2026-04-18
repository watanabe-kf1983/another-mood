# 本プロジェクトのドキュメントについて

本プロジェクトはドキュメント生成ツール another-mood を用いて文書を管理しています。開発者向けの内部設計書は `dev-docs/` に、利用者に供給するサンプルプロジェクト群（user-guide / starter / examples）は `showcase/` にあります。

## ドキュメントを読むには

以下のコマンドで開発者向けドキュメントをビルドする（Python CLI ツール。動かない場合は下記参照）:

```bash
mood build dev-docs
```

ビルドされたドキュメントは `.another-mood/dev-docs/output/` に出力される。

起点: [.another-mood/dev-docs/output/prose/index.md](../.another-mood/dev-docs/output/prose/index.md)

`showcase/` 配下のサンプルプロジェクトも同じ要領でビルドできる:

```bash
mood build showcase/examples/ecommerce
```

コマンドが動かない場合は、[uv](https://docs.astral.sh/uv/) をインストールし `uv sync` を実行する。

## ドキュメントを編集するには

ソース (`dev-docs/contents/`) を編集する場合、`mood watch` を使うとファイル変更を検知して自動でリビルドされる:

```bash
mood watch dev-docs
```

> **このプロジェクトの開発時**: another-mood 自身の Python コードを変更する場合、`mood watch` は古いコードで動き続ける。そのため `mood build dev-docs` をつど実行する。
