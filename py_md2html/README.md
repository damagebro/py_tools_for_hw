# py_md2html

`py_md2html` 将单个 Markdown 文档转换为可离线打开的完整 HTML 页面，适合发布工具 README、设计说明和评审文档。

## 主要功能

- 支持 Markdown 表格、围栏代码块、脚注和常用扩展语法。
- 可选自动生成目录、为未编号标题补充层级编号。
- 输出完整 HTML 和内置 CSS，不依赖外部样式文件。
- 使用源 Markdown 所在目录作为相对图片和链接的解析根目录。
- 支持 Windows、Linux 和 macOS 下的绝对路径或相对路径。

## 安装依赖

```bash
python -m pip install -r requirements.txt
```

Markdown 转换基于 Python-Markdown 的 `extra`、`sane_lists` 和 `toc` 扩展。

## 常用命令

在 Markdown 同目录生成同名 HTML：

```bash
python -B src/py_md2html.py README.md
```

指定输出文件：

```bash
python -B src/py_md2html.py README.md -o out/README.html
```

在正文前增加自动目录，并补充章节编号：

```bash
python -B src/py_md2html.py README.md --toc --number-headings
```

通过 `hw_tool` 调用：

```bash
hw_tool md2html README.md -o README.html
```

## 完整参数

| parameter           | description                                       |
| ------------------- | ------------------------------------------------- |
| `input`             | 输入 `.md` 或 `.markdown` 文件。                  |
| `-o, --output`      | 输出 `.html` 或 `.htm` 文件，默认与输入文件同名。 |
| `--title`           | 覆盖 HTML `<title>`，默认取第一个一级标题。       |
| `--toc`             | 在正文前插入自动生成的目录。                      |
| `--number-headings` | 为未编号标题补充层级编号，保留已有编号。          |
| `--version`         | 显示工具版本。                                    |

## 目录与编号

VS Code 的 Markdown HTML 预览和导出固定使用 `--toc --number-headings`，不弹出 TOC 选择框。正文和目录同步补充 `1.`、`1.1` 等层级编号，已有编号保留并用于后续编号续接；唯一且位于首个标题位置的未编号一级标题作为文档名，不补编号。代码块和普通列表不参与编号，Markdown 源文件与原有标题锚点保持不变。普通 CLI 仍按需显式传入这两个独立选项。

## 相对资源

生成页面使用 `<base>` 指向源 Markdown 所在目录。因此，即使 HTML 输出到其他目录，`![diagram](assets/diagram.png)` 仍会访问 Markdown 同目录下的 `assets/diagram.png`。移动源文档及其资源目录后，需要重新生成 HTML。

## 回归测试

```bash
python -B test/test_py_md2html.py
```
