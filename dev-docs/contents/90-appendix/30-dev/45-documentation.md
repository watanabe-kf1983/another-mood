# ドキュメントの書き方 (appendix)

[ドキュメントの書き方](../../30-dev/45-documentation.md) の背景。

## appendix を ADR 型のレコードにしない理由

appendix の過程のログを ADR（Architecture Decision Record）に倣ったレコードに分ける案を検討し、採らなかった。案は、判断・理由・却下案・帰結・PR 番号を持ち設計文書に紐づく decisions、設計文書と fixture に紐づく rules、`## Proposals` 節から独立させ task に紐づく proposals の三種を entity にし、design ページを join で描くもの（タスク W5、取り下げ）。

- **残したいものは appendix で足りている**: 判断した時点の文脈と却下案を残し、本文から追い出すという ADR の利点は、design / dev と鏡写しの appendix で既に得ている。ADR の型（Status、superseded の鎖、承認後は書き換えない原則）は、それに上乗せする運用の重さに見合わない
- **ADR は現状を散らす**: ADR は出来事のログで、現状を知るには関連する記録を集めて superseded を差し引く必要がある。意図の一文を設計と同じ場所に書き別の体系で索引しないのはこの弱点を避けるためで、過程まで ADR 化すると逆向きの力が働く
- **Proposal は育つ草稿で、ADR の proposed と性格が違う**: ADR の proposed はレビュー期間だけの状態だが、本プロジェクトの Proposal はタスクの進行につれて何度も更新される。設計文書に近く、書き換えない記録の型に乗らない
- **二ファイル運用の摩擦**: prose は属性を持てないので、レコード化すると YAML + Markdown の二ファイルで書くことになり、判断を残すたびにその手間を払う

技術的には成り立つことは試作で確かめた。grouped ビューのキーを `id` に昇格させれば、サブテンプレートから `node()` で設計文書ごとの decisions を引いて design ページ末尾に一覧でき、`node()` で引いたレコードの属性（PR 番号など）も読める。proposal から task への逆引きも flatten + grouped で書ける。取り下げは実現性ではなく、得るものの小ささによる。

再検討の契機: tasks.yaml とロードマップが退役すると、dev-docs から構造化データが消え、dog-fooding の題材を失う。その後継を求める段になれば、ADR の弱点（散らばる、話題で引けない、superseded を辿る必要がある）が join で解ける種類の問題であることは、題材としての魅力として残る。
