# py_md2html

`py_md2html` 将单个 Markdown 文档转换为可离线打开的完整 HTML 页面，适合发布工具 README、设计说明和评审文档。

## 主要功能

- 支持 Markdown 表格、围栏代码块、脚注和常用扩展语法。
- 可选自动生成目录。
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

在正文前增加自动目录：

```bash
python -B src/py_md2html.py README.md --toc
```

通过 `hw_tool` 调用：

```bash
hw_tool md2html README.md -o README.html
```

## 完整参数

| parameter      | description                                           |
| -------------- | ----------------------------------------------------- |
| `input`        | 输入 `.md` 或 `.markdown` 文件。                      |
| `-o, --output` | 输出 `.html` 或 `.htm` 文件，默认与输入文件同名。     |
| `--title`      | 覆盖 HTML `<title>`，默认取第一个一级标题。            |
| `--toc`        | 在正文前插入自动生成的目录。                          |
| `--version`    | 显示工具版本。                                        |

## 相对资源

生成页面使用 `<base>` 指向源 Markdown 所在目录。因此，即使 HTML 输出到其他目录，`![diagram](assets/diagram.png)` 仍会访问 Markdown 同目录下的 `assets/diagram.png`。移动源文档及其资源目录后，需要重新生成 HTML。

## 回归测试

```bash
python -B test/test_py_md2html.py
```
