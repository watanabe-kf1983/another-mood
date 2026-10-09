# プロジェクト構成

## External Design

- contents / views / templates の三層は MS-Access の Table / Query / Form・Report に対応する。ビューを YAML DSL で書くのはこの対応から（[背景](../../90-appendix/20-design/20-app/10-project-structure.md#ms-access-アナロジー)）
- CLI は出力 `.another-mood/` を `<projectDir>` の中ではなく CWD 直下に置く。入力ディレクトリはユーザのコンテンツ領域で、生成物を書き込まないため。利用者への約束は `docs/reference/cli.md` の `<project_dir>` 節、理由の全体は[背景](../../90-appendix/20-design/20-app/10-project-structure.md#cli-が-another-mood-を-cwd-直下に配置する理由)
