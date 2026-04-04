# Booksmith

[English](README.md) | [简体中文](README.zh-CN.md) | [日本語](README.ja.md)

Booksmith は、文字ベースの PDF と EPUB 書籍を簡体字中国語に翻訳するための CLI ツールです。同じ基盤の上で、次の 2 つのワークフローを提供します。

- `engineering`: 大量処理向けの、正確で再開可能かつコストを抑えた翻訳
- `publishing`: 非フィクション向けの高品質翻訳。段階的な修正、校正、最終レビュー、構造化された原文監査、仲裁、深度レビューを含みます

## GUI

デスクトップ GUI は CLI と同じ翻訳パイプラインを共有する、独立したローカル入口です。CLI の代替ではなく、補助的なインターフェースです。

工程モードと出版モードを切り替えながら、進捗、ログ、結果ビューを見たい場合は GUI を使ってください。自動化、スクリプト化、バッチ処理が目的なら CLI の方が適しています。

GUI は次のいずれかで起動できます。

```bash
booksmith-gui
python -m booksmith.gui
```

## 機能

- 文字ベースの PDF / EPUB から本文を抽出
- まずブックマークまたは TOC を優先し、必要に応じて見出し規則へフォールバック
- 章ごとに分割して並列翻訳
- OpenAI / Gemini API に対応
- リトライ可能なエラーに指数バックオフで再試行
- 中断後の再開と、段階的な再実行に対応
- 読みやすい中国語の整形 PDF を生成
- 構造化された出版パイプラインから再フロー可能な EPUB を生成
- 原文監査、レビュー合意、修復ログ、QA スクリーンショットを出力

## インストール

### 標準 Python

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -e .[dev]
```

### Conda の代替案

ローカル Python が依存関係と互換性がない場合:

```bash
conda create -n booksmith-py311 python=3.11
conda activate booksmith-py311
pip install -e .[dev]
```

## 設定

`.env.example` をコピーし、必要な API Key を設定してください。

- `OPENAI_API_KEY`
- `GEMINI_API_KEY`

## 使い方

### 工程モード

```bash
booksmith engineering --input ./books --output ./out --provider gemini --resume
```

### 出版モード

```bash
booksmith publishing --input ./books --output ./out --provider openai --model gpt-4o-mini
```

デフォルトの出力は入力形式に従います。

- `PDF` 入力なら主出力は `publishing/final/translated.pdf`
- `EPUB` 入力なら主出力は `publishing/final/translated.epub`

クロスフォーマット出力は明示的に指定してください。

```bash
booksmith publishing --input ./books/book.pdf --output ./out --also-epub
booksmith publishing --input ./books/book.epub --output ./out --also-pdf
```

後続の編集段階だけを再実行する場合:

```bash
booksmith publishing --input ./books --output ./out --from-stage revision --to-stage final-review
```

原文対照の `deep-review` を実行し、最終成果物を再生成する場合:

```bash
booksmith publishing --input ./books --output ./out --from-stage final-review --to-stage deep-review --render-pdf
```

用語集だけを生成して確認する場合:

```bash
booksmith publishing --input ./books --output ./out --to-stage lexicon
```

既存ワークスペースから、翻訳 API を再度呼ばずに整形 PDF を再生成する場合:

```bash
booksmith render-pdf --workspace ./out/book-name
```

指定した PDF ページを PNG として書き出す場合:

```bash
booksmith render-pages --pdf ./out/book-name/translated.pdf --output-dir ./tmp/pages --pages 1,3-5
```

ワークスペース内の visual QA 用スクリーンショットを生成する場合:

```bash
booksmith qa-pdf --workspace ./out/book-name
```

工程版 PDF が存在せず、`publishing/final/translated.pdf` が存在する場合、`qa-pdf` は出版版 PDF を使用し、スクリーンショットを `publishing/qa/` に書き出します。

## 各書籍の出力

処理された各書籍は、出力ルート配下に専用ワークスペースとして保存されます。

### 工程出力

- `manifest.json`
- `chunks.jsonl`
- `translations.jsonl`
- `error_log.json`
- `run_summary.json`
- `translated.txt`
- `translated.pdf`
- `qa/pages/page-###.png`
- `qa/qa_summary.json`

### 出版出力

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

`--to-stage deep-review` を実行した場合、さらに次が生成されます。

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

### 共通の翻訳オプション

- `--input`: 単一ファイルまたはディレクトリ。ディレクトリは再帰的に走査します
- `--output`: 出力ルート
- `--provider`: `openai` または `gemini`
- `--model`: デフォルトモデルの上書き
- `--api-key-env`: API Key 環境変数名の上書き
- `--max-concurrency`: 同時翻訳リクエスト数の上限
- `--resume/--no-resume`: 成功済みチャンクを可能な範囲で再利用
- `--force`: 対象書籍の旧状態を削除して最初からやり直し
- `--glossary`: 用語対応 JSON
- `--name-map`: 固有名詞対応 JSON
- `--chapter-strategy`: `toc-first`、`auto`、`rule-only`、`manual`
- `--manual-toc`: `--chapter-strategy manual` で使う JSON の章タイトル一覧
- `--chunk-size`: 1 チャンクあたりのおおよその最大ソーステキスト語数
- `--render-pdf/--no-render-pdf`: 翻訳後に整形 PDF を生成するかどうか

### 出版専用オプション

- `--style`: 出版スタイル設定。現在は `non-fiction-publishing`
- `--from-stage`: `draft`、`lexicon`、`revision`、`proofread`、`final-review`、`deep-review`
- `--to-stage`: 指定した出版段階で停止
- `--also-pdf`: 主出力が EPUB の場合に PDF を追加出力
- `--also-epub`: 主出力が PDF の場合に EPUB を追加出力
- `--audit-depth`: `standard` または `consensus`
- `--enable-cross-review/--no-cross-review`: 監査 / レビュー仲裁ループの有効化・無効化
- `--image-policy`: 現在は `extract-or-preserve-caption`

出版段階の意味:

- `draft`: 全書の初回翻訳
- `lexicon`: 全書の用語・固有名詞・決定ファイル
- `revision`: 用語集に基づく章単位の修正
- `proofread`: 独立した校正とノート出力
- `final-review`: 全書の整合性確認と最終テキスト / PDF / EPUB 出力
- `deep-review`: 原文対照の受け入れ検査。監査結果と監査成果物を出力し、選択された出力形式に従って最終テキスト / PDF / EPUB を再生成

## 検証

```bash
ruff check .
pytest -q
```

## 注意

- 現在のバージョンは文字ベースの PDF のみに対応しており、スキャン PDF は未対応です。
- 工程モードは中国語のプレーンテキストと、任意の整形 PDF を出力します。
- 出版モードは非フィクション向けの出版風中国語を対象とし、中間編集成果物を保持します。
- `resume` はデフォルトで有効です。書籍を最初からやり直すには `--force` を使用してください。
- 出版モードの `resume` はステージ単位です。`--from-stage` と `--to-stage` で一部の編集工程だけを再実行できます。
- 整形 PDF はローカルの Windows 中国語フォントを使用し、元 PDF のページレイアウトを逐一再現するのではなく、書籍らしいレイアウトを目指しています。
