# Paging Specification

ファイル分割戦略の仕様。ドキュメントのページ分割とプロファイル切り替えを定義する。

## paging.yaml

`presentation/paging.yaml` にクラスとファイルパステンプレートのマッピングを定義する。プロファイルとして複数定義し、用途に応じて切り替える:

```yaml
# presentation/paging.yaml
profiles:
  web:
    pages:
      - class: erd
        path: "erd/{{ key }}.md"
      - class: erd.entity
        path: "erd/{{ key }}/entities.md"
  pdf:
    pages:
      - class: erd
        path: "all.md"
```

## 分割ルール

- paging 設定に列挙されたクラスが分割単位
- 列挙されていないクラスの `{% section %}` はインライン展開される
- paging に列挙できるのは `key` を持つクラスに限られる（ファイル名生成に `key` が必要なため。key/ID 体系は [anchor-spec.md](anchor-spec.md) 参照）

## `{% section %}` との関係

テンプレートの `{% section %}` タグは paging 設定に応じて振る舞いが変わる:

- 対象クラスが paging の分割単位 → 別ファイルに出力し、親にはリンクを残す
- 分割単位でない → インライン展開（通常の `{% include %}` と同等）

テンプレート作者は paging を意識しない。同じテンプレートが Web 用（分割）でも PDF 用（全部インライン）でもそのまま動く。
