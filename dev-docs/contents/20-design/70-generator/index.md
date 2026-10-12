# Generator

生成フェーズの設計仕様。Generator は Composer が出した木を inert に詰め替え、各ノードにメタデータを注入し（[anchor-spec.md](30-anchor-spec.md#ノードメタデータ)）、edition ごとにテンプレートで Markdown ページに描く（[template-spec.md](20-template-spec.md)）。テンプレートに何を許すかは[信頼モデル](25-template-trust-model.md)、ページとマウントの置き場所は[出力の構成](40-output-layout.md)。描いた後の最終出力は Reconcile が確定する（[ビルドレポート](../75-meta-documentation/30-build-report.md)）。
