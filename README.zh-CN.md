# Booksmith

[English](README.md) | [简体中文](README.zh-CN.md) | [日本語](README.ja.md)

Booksmith 是一个用于将文字版 PDF 和 EPUB 图书翻译成简体中文的命令行工具。它在同一套底层能力上提供两条工作流：

- `engineering`：面向批量处理的准确、可续跑、成本可控翻译
- `publishing`：面向非虚构图书的高质量翻译，包含分阶段修订、校对、终审、结构化原文审计、仲裁和深度复核

## GUI

桌面 GUI 是一个独立的本地入口，与 CLI 共享同一套翻译流水线。它是 CLI 的补充，不是替代品。

如果你希望在本地通过图形界面操作，并查看工程化模式、出版级模式、进度、日志和结果视图，可以使用 GUI。若需要自动化、脚本化或批量处理，则使用 CLI。

可以通过下面任一命令启动 GUI：

```bash
booksmith-gui
python -m booksmith.gui
```

## 功能

- 从文字版 PDF / EPUB 中提取文本
- 优先通过书签或目录保留章节结构，再回退到标题规则
- 按章节分块并发翻译
- 支持 OpenAI 和 Gemini API
- 对可恢复错误使用指数退避重试
- 支持断点续跑和分阶段重跑
- 生成适合阅读的中文精排 PDF
- 从结构化出版流水线生成可重排 EPUB
- 输出原文审计、共识结果、修复日志和 QA 截图

## 安装

### 标准 Python

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -e .[dev]
```

### Conda 备用方案

如果本地 Python 与依赖不兼容：

```bash
conda create -n booksmith-py311 python=3.11
conda activate booksmith-py311
pip install -e .[dev]
```

## 配置

复制 `.env.example`，然后设置对应的 API Key：

- `OPENAI_API_KEY`
- `GEMINI_API_KEY`

## 用法

### 工程化模式

```bash
booksmith engineering --input ./books --output ./out --provider gemini --resume
```

### 出版级模式

```bash
booksmith publishing --input ./books --output ./out --provider openai --model gpt-4o-mini
```

默认输出会跟随输入格式：

- 输入 `PDF` 时，主输出为 `publishing/final/translated.pdf`
- 输入 `EPUB` 时，主输出为 `publishing/final/translated.epub`

跨格式输出需要显式开启：

```bash
booksmith publishing --input ./books/book.pdf --output ./out --also-epub
booksmith publishing --input ./books/book.epub --output ./out --also-pdf
```

只重跑后续编辑阶段：

```bash
booksmith publishing --input ./books --output ./out --from-stage revision --to-stage final-review
```

运行原文对照 `deep-review`，并重建最终交付物：

```bash
booksmith publishing --input ./books --output ./out --from-stage final-review --to-stage deep-review --render-pdf
```

只生成术语表，方便检查：

```bash
booksmith publishing --input ./books --output ./out --to-stage lexicon
```

在已有工作区上重新生成精排 PDF，而不再次调用翻译 API：

```bash
booksmith render-pdf --workspace ./out/book-name
```

导出指定 PDF 页为 PNG：

```bash
booksmith render-pages --pdf ./out/book-name/translated.pdf --output-dir ./tmp/pages --pages 1,3-5
```

生成工作区内的视觉 QA 截图集：

```bash
booksmith qa-pdf --workspace ./out/book-name
```

如果工程版 PDF 不存在，但 `publishing/final/translated.pdf` 存在，`qa-pdf` 会自动使用出版版 PDF，并将截图写入 `publishing/qa/`。

## 每本书的输出

每个处理完成的书都会在输出根目录下生成独立的工作区目录。

### 工程化输出

- `manifest.json`
- `chunks.jsonl`
- `translations.jsonl`
- `error_log.json`
- `run_summary.json`
- `translated.txt`
- `translated.pdf`
- `qa/pages/page-###.png`
- `qa/qa_summary.json`

### 出版级输出

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

当运行 `--to-stage deep-review` 时，还会额外生成：

- `publishing/deep_review/findings.jsonl`
- `publishing/deep_review/revised_chapters.jsonl`
- `publishing/deep_review/decisions.json`
- `publishing/audit/source_audit.jsonl`
- `publishing/audit/review_audit.jsonl`
- `publishing/audit/consensus.json`
- `publishing/audit/final_audit_report.json`
- `publishing/assets/manifest.json`
- `publishing/assets/images/*`

## CLI 参数

### 通用翻译参数

- `--input`：单个文件或目录，目录会递归扫描
- `--output`：输出根目录
- `--provider`：`openai` 或 `gemini`
- `--model`：覆盖默认模型
- `--api-key-env`：覆盖 API Key 环境变量名
- `--max-concurrency`：最大并发翻译请求数
- `--resume/--no-resume`：尽可能复用已成功的块结果
- `--force`：删除目标书籍的旧状态并重新开始
- `--glossary`：术语映射 JSON 文件
- `--name-map`：专名映射 JSON 文件
- `--chapter-strategy`：`toc-first`、`auto`、`rule-only` 或 `manual`
- `--manual-toc`：在 `--chapter-strategy manual` 时使用的章节标题 JSON 列表
- `--chunk-size`：每个块的大致最大源文本词数
- `--render-pdf/--no-render-pdf`：翻译后是否输出精排 PDF

### 出版级专用参数

- `--style`：出版风格配置，目前是 `non-fiction-publishing`
- `--from-stage`：`draft`、`lexicon`、`revision`、`proofread`、`final-review` 或 `deep-review`
- `--to-stage`：在某个出版阶段后停止
- `--also-pdf`：当主输出默认是 EPUB 时，额外输出 PDF
- `--also-epub`：当主输出默认是 PDF 时，额外输出 EPUB
- `--audit-depth`：`standard` 或 `consensus`
- `--enable-cross-review/--no-cross-review`：是否启用审校/复核仲裁闭环
- `--image-policy`：当前为 `extract-or-preserve-caption`

出版阶段语义：

- `draft`：整书初译
- `lexicon`：整书术语、专名和决策文件
- `revision`：基于术语表的章节修订
- `proofread`：独立校对并输出笔记
- `final-review`：整书一致性检查并生成最终文本 / PDF / EPUB
- `deep-review`：原文对照验收，输出审计结果和审计产物，然后按所选输出格式重建最终文本 / PDF / EPUB

## 验证

```bash
ruff check .
pytest -q
```

## 说明

- 当前版本只支持文字版 PDF，不支持扫描版 PDF。
- 工程化模式会输出中文纯文本，以及可选的精排 PDF。
- 出版级模式面向非虚构、正式出版风格的中文，并保留中间编辑产物。
- 默认启用 `resume`；如需从头重跑整本书，请使用 `--force`。
- 出版级 `resume` 是分阶段的；可以用 `--from-stage` 和 `--to-stage` 精确重跑局部流程。
- 精排 PDF 使用本机 Windows 中文字体，目标是接近书稿风格，而不是逐页复制源 PDF 的视觉设计。
