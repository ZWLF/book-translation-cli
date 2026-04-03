# book-translation-cli

[English](README.md) | [简体中文](README.zh-CN.md) | [日本語](README.ja.md)

这是一个面向文字版 PDF 和 EPUB 图书的命令行翻译工具。它同时提供两条工作流：一条偏工程化，适合快速批量翻译；一条偏出版级，支持原文对照审计、结构化修复、精排 PDF 和可重排 EPUB 输出。

## 模式

- `engineering`：强调准确、可恢复、成本可控，适合批量处理
- `publishing`：强调质量优先，适合非虚构图书，带修订、校对、终审、结构化审计和深度复核

为了兼容旧用法，顶层命令仍然是 `engineering` 的别名。

## 功能

- 从文字版 PDF 和 EPUB 中提取正文
- 优先利用书签或目录保留章节结构，再回退到标题规则
- 按章节分块并发翻译
- 支持 OpenAI 和 Gemini API
- 对可恢复错误做指数退避重试
- 支持断点续跑和分阶段重跑
- 生成适合阅读的中文精排 PDF
- 从出版级结构化内容生成可重排 EPUB
- 输出原文对照审计、复核共识、修复记录和视觉 QA 截图

## 安装

### 标准 Python

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -e .[dev]
```

### Conda 兜底方案

如果本地 Python 与依赖不兼容：

```bash
conda create -n book-translation-cli-py311 python=3.11
conda activate book-translation-cli-py311
pip install -e .[dev]
```

## 配置

复制 `.env.example`，然后设置对应的 API Key：

- `OPENAI_API_KEY`
- `GEMINI_API_KEY`

## 用法

### 工程化模式

```bash
book-translator engineering --input ./books --output ./out --provider gemini --resume
```

兼容别名：

```bash
book-translator --input ./books --output ./out --provider gemini --resume
```

### 出版级模式

```bash
book-translator publishing --input ./books --output ./out --provider openai --model gpt-4o-mini
```

默认输出会跟随输入格式：

- 输入 `PDF` 时，主输出是 `publishing/final/translated.pdf`
- 输入 `EPUB` 时，主输出是 `publishing/final/translated.epub`

跨格式输出必须显式指定：

```bash
book-translator publishing --input ./books/book.pdf --output ./out --also-epub
book-translator publishing --input ./books/book.epub --output ./out --also-pdf
```

如果只想从后半段出版流程继续跑：

```bash
book-translator publishing --input ./books --output ./out --from-stage revision --to-stage final-review
```

运行原文对照 `deep-review` 并重建最终交付物：

```bash
book-translator publishing --input ./books --output ./out --from-stage final-review --to-stage deep-review --render-pdf
```

如果只想先生成术语表：

```bash
book-translator publishing --input ./books --output ./out --to-stage lexicon
```

无需重新调用翻译 API，直接从已有工作区重新生成 PDF：

```bash
book-translator render-pdf --workspace ./out/book-name
```

把指定 PDF 页面导出成 PNG：

```bash
book-translator render-pages --pdf ./out/book-name/translated.pdf --output-dir ./tmp/pages --pages 1,3-5
```

生成工作区内的视觉 QA 截图集：

```bash
book-translator qa-pdf --workspace ./out/book-name
```

如果工程版 PDF 不存在，但 `publishing/final/translated.pdf` 存在，`qa-pdf` 会自动使用出版版 PDF，并把截图写到 `publishing/qa/`。

## 每本书的输出

每本处理完成的书都会在输出根目录下生成独立工作区。

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

当 `--to-stage deep-review` 运行时，还会额外生成：

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

- `--input`：单文件或目录，目录会递归扫描
- `--output`：输出根目录
- `--provider`：`openai` 或 `gemini`
- `--model`：覆盖默认模型
- `--api-key-env`：覆盖默认 API Key 环境变量名
- `--max-concurrency`：最大并发请求数
- `--resume/--no-resume`：是否复用已成功的块结果
- `--force`：删除目标书籍的旧状态并全量重跑
- `--glossary`：JSON 术语映射文件
- `--name-map`：JSON 专名映射文件
- `--chapter-strategy`：`toc-first`、`auto`、`rule-only` 或 `manual`
- `--manual-toc`：当 `--chapter-strategy manual` 时使用的 JSON 目录列表
- `--chunk-size`：每个块的大致原文字数上限
- `--render-pdf/--no-render-pdf`：是否在翻译后渲染精排 PDF

### 出版级专用参数

- `--style`：出版风格配置，目前为 `non-fiction-publishing`
- `--from-stage`：`draft`、`lexicon`、`revision`、`proofread`、`final-review` 或 `deep-review`
- `--to-stage`：在某个出版阶段结束
- `--also-pdf`：当主输出默认是 EPUB 时，额外输出 PDF
- `--also-epub`：当主输出默认是 PDF 时，额外输出 EPUB
- `--audit-depth`：`standard` 或 `consensus`
- `--enable-cross-review/--no-cross-review`：启用或关闭审计/复核仲裁循环
- `--image-policy`：当前支持 `extract-or-preserve-caption`

出版阶段语义：

- `draft`：整书初译
- `lexicon`：生成全书术语、专名和决策文件
- `revision`：基于术语表做章节修订
- `proofread`：独立校对并输出校对说明
- `final-review`：整书一致性检查并生成最终文本/PDF
- `deep-review`：做原文对照验收，输出审计产物，并按指定输出格式重建最终文本/PDF/EPUB

## 验证

```bash
ruff check .
pytest -q
```

## 说明

- 当前版本只支持文字版 PDF，不支持扫描版 PDF。
- `engineering` 模式输出中文纯文本，以及可选的精排 PDF。
- `publishing` 模式面向非虚构中文译本，并保留中间审校产物。
- 默认开启 `resume`；如果想整本重跑，请使用 `--force`。
- 出版级 `resume` 是分阶段的，可配合 `--from-stage` 和 `--to-stage` 精确重跑。
- 精排 PDF 使用本机 Windows 中文字体生成，目标是适合阅读的书稿版式，而不是逐页复刻原版 PDF。
