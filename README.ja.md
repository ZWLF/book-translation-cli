# book-translation-cli

[English](README.md) | [简体中文](README.zh-CN.md) | [日本語](README.ja.md)

テキストベースの PDF / EPUB 書籍を簡体字中国語へ翻訳するための CLI ツールです。高速なバッチ処理向けの `engineering` ワークフローと、原文監査・構造化修復・整形 PDF・リフロー可能 EPUB を含む高品質な `publishing` ワークフローを備えています。

## モード

- `engineering`: 正確性、再開性、コスト管理を重視したバッチ翻訳
- `publishing`: 品質優先のノンフィクション向け翻訳。改稿、校正、最終レビュー、構造化監査、深度レビューを含みます

互換性のため、トップレベルコマンドは引き続き `engineering` のエイリアスです。

## 主な機能

- テキストベースの PDF / EPUB から本文を抽出
- しおりや TOC を優先して章構造を保持し、必要に応じて見出し規則へフォールバック
- 章単位の分割と並列翻訳
- OpenAI / Gemini API の両対応
- 回復可能な API エラーに対する指数バックオフ付きリトライ
- 中断後の再開とステージ単位の再実行
- 読書向けに整えた中国語 PDF の生成
- 構造化された出版ワークフローからのリフロー可能 EPUB 生成
- 原文監査、レビュー合意、修復ログ、視覚 QA スクリーンショットの出力

## インストール

### 標準 Python

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -e .[dev]
```

### Conda フォールバック

ローカル Python が依存関係と互換しない場合:

```bash
conda create -n book-translation-cli-py311 python=3.11
conda activate book-translation-cli-py311
pip install -e .[dev]
```

## 設定

`.env.example` をコピーし、必要な API キーを設定します。

- `OPENAI_API_KEY`
- `GEMINI_API_KEY`

## 使い方

### Engineering モード

```bash
book-translator engineering --input ./books --output ./out --provider gemini --resume
```

互換エイリアス:

```bash
book-translator --input ./books --output ./out --provider gemini --resume
```

### Publishing モード

```bash
book-translator publishing --input ./books --output ./out --provider openai --model gpt-4o-mini
```

デフォルトの出力形式は入力形式に従います。

- `PDF` 入力なら主出力は `publishing/final/translated.pdf`
- `EPUB` 入力なら主出力は `publishing/final/translated.epub`

クロスフォーマット出力は明示的に指定します。

```bash
book-translator publishing --input ./books/book.pdf --output ./out --also-epub
book-translator publishing --input ./books/book.epub --output ./out --also-pdf
```

後半の編集ステージだけ再開する場合:

```bash
book-translator publishing --input ./books --output ./out --from-stage revision --to-stage final-review
```

原文対照 `deep-review` を実行し、最終成果物を再構築する場合:

```bash
book-translator publishing --input ./books --output ./out --from-stage final-review --to-stage deep-review --render-pdf
```

用語集だけ先に確認したい場合:

```bash
book-translator publishing --input ./books --output ./out --to-stage lexicon
```

翻訳 API を呼ばずに既存ワークスペースから PDF を再生成する場合:

```bash
book-translator render-pdf --workspace ./out/book-name
```

特定の PDF ページを PNG として書き出す場合:

```bash
book-translator render-pages --pdf ./out/book-name/translated.pdf --output-dir ./tmp/pages --pages 1,3-5
```

ワークスペース内に視覚 QA 用のスナップショット群を生成する場合:

```bash
book-translator qa-pdf --workspace ./out/book-name
```

Engineering PDF がなくても `publishing/final/translated.pdf` があれば、`qa-pdf` は出版版 PDF を使い、スクリーンショットを `publishing/qa/` に出力します。

## 書籍ごとの出力

処理された各書籍ごとに、出力先の下に専用ワークスペースが作成されます。

### Engineering 出力

- `manifest.json`
- `chunks.jsonl`
- `translations.jsonl`
- `error_log.json`
- `run_summary.json`
- `translated.txt`
- `translated.pdf`
- `qa/pages/page-###.png`
- `qa/qa_summary.json`

### Publishing 出力

- `publishing/manifest.json`
- `publishing/state/<stage>.json`
- `publishing/draft/chapters.jsonl`
- `publishing/draft/draft.txt`
- `publishing/lexicon/glossary.json`
- `publishing/lexicon/names.json`
- `publishing/lexicon/decisions.json`
- `publishing/revision/revised_chapters.jsonl`
- `publishing/proofread/proofread_notes.jsonl`
- `publishing/proofread/proofread_changes.jsonl`
- `publishing/final/final_chapters.jsonl`
- `publishing/final/translated.txt`
- `publishing/final/translated.pdf`
- `publishing/final/translated.epub`
- `publishing/editorial_log.json`
- `publishing/run_summary.json`
- `publishing/qa/pages/page-###.png`
- `publishing/qa/qa_summary.json`

`--to-stage deep-review` を実行すると、さらに以下が生成されます。

- `publishing/deep_review/findings.jsonl`
- `publishing/deep_review/revised_chapters.jsonl`
- `publishing/deep_review/decisions.json`
- `publishing/audit/source_audit.jsonl`
- `publishing/audit/review_audit.jsonl`
- `publishing/audit/consensus.json`
- `publishing/audit/final_audit_report.json`
- `publishing/assets/manifest.json`
- `publishing/assets/images/*`

## CLI オプション

### 共通翻訳オプション

- `--input`: 単一ファイルまたはディレクトリ。ディレクトリは再帰的に走査
- `--output`: 出力ルートディレクトリ
- `--provider`: `openai` または `gemini`
- `--model`: デフォルトモデルを上書き
- `--api-key-env`: API キー環境変数名を上書き
- `--max-concurrency`: 同時実行リクエスト数
- `--resume/--no-resume`: 成功済みチャンクを再利用するか
- `--force`: 対象書籍の旧状態を削除して最初から再実行
- `--glossary`: 用語マッピング用 JSON
- `--name-map`: 固有名詞マッピング用 JSON
- `--chapter-strategy`: `toc-first`、`auto`、`rule-only`、`manual`
- `--manual-toc`: `--chapter-strategy manual` 用の JSON 目次リスト
- `--chunk-size`: 1 チャンクあたりの原文語数の目安上限
- `--render-pdf/--no-render-pdf`: 翻訳後に整形 PDF を生成するかどうか

### Publishing 専用オプション

- `--style`: 出版スタイル設定。現在は `non-fiction-publishing`
- `--from-stage`: `draft`、`lexicon`、`revision`、`proofread`、`final-review`、`deep-review`
- `--to-stage`: 指定した出版ステージで停止
- `--also-pdf`: 主出力が EPUB のとき追加で PDF も出力
- `--also-epub`: 主出力が PDF のとき追加で EPUB も出力
- `--audit-depth`: `standard` または `consensus`
- `--enable-cross-review/--no-cross-review`: 監査 / レビュー / 仲裁ループを有効化または無効化
- `--image-policy`: 現在は `extract-or-preserve-caption`

出版ステージの意味:

- `draft`: 全書の初訳
- `lexicon`: 全書の用語集・固有名詞・判断記録を生成
- `revision`: 用語集に基づく章単位の改稿
- `proofread`: 独立した校正と校正ノートの出力
- `final-review`: 全書整合性レビューと最終テキスト / PDF の生成
- `deep-review`: 原文対照の受け入れレビューを行い、監査成果物を出力しつつ、指定フォーマットに応じて最終テキスト / PDF / EPUB を再構築

## 検証

```bash
ruff check .
pytest -q
```

## 注意事項

- 現バージョンはテキストベースの PDF のみ対応し、スキャン PDF には未対応です。
- `engineering` は中国語のテキストと任意の整形 PDF を出力します。
- `publishing` はノンフィクション向けの出版品質中国語訳を目標とし、中間編集成果物も保持します。
- `resume` はデフォルトで有効です。最初からやり直す場合は `--force` を使ってください。
- 出版ワークフローの `resume` はステージ単位です。`--from-stage` と `--to-stage` で部分再実行できます。
- 整形 PDF はローカルの Windows 中国語フォントを使った読書向けレイアウトであり、原書 PDF のページ単位複製ではありません。
