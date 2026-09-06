# hw_tool 发布与使用

本文说明如何生成 `hw_tool 0.5.0` 发布包，以及发布后在 Windows、Linux 和 VS Code 中使用。命令默认在 `py_tools_for_hw` 仓库根目录执行。

## 1. 生成发布包

### 1.1 环境依赖

发布脚本需要 Python 3.11+。各工具运行时还需要以下 Python 包：

```bash
python -m pip install jinja2 openpyxl Markdown PyYAML
```

发布包不内置 Python。无网络环境应提前准备公共 Python venv 或内部 wheelhouse。

### 1.2 开发发布

开发发布直接使用当前工作区，包括未提交修改，适合本地验证：

```bash
python -B hw_tool/publish/release.py --version 0.5.0-dev.1
```

### 1.3 正式发布

正式发布从注册的 Git URL 获取指定 tag，也可以指定完整的 40 位 commit ID：

```bash
python -B hw_tool/publish/release.py --version 0.5.0 --official \
    --repo-ref py_tools_for_hw=v0.5.0
```

正式发布不接受 branch。tag 需要提前创建，发布脚本不会创建或推送 tag。增加 `--shallow` 可以只获取所选版本的浅层历史。

Linux 安装位置不是默认的 `/tools/hw_tool` 时，需要在发布阶段指定实际路径：

```bash
python -B hw_tool/publish/release.py --version 0.5.0 --official \
    --repo-ref py_tools_for_hw=v0.5.0 \
    --linux-install-root /opt/company/hw_tool
```

### 1.4 发布产物

```text
hw_tool/publish/out/hw_tool-0.5.0/
├── hw_tool/                       # Windows/Linux 独立源码目录
├── modulefiles/hw_tool/0.5.0      # Linux modulefile
├── hw_tool-0.5.0.zip              # Windows/Linux 源码包
├── dmg-hw-tool-0.5.0.vsix         # VS Code 插件
└── SHA256SUMS                     # 完整性校验清单
```

同一版本已存在时，发布脚本会拒绝覆盖。需要重新生成时，应先人工确认并处理旧产物，或使用新的版本号。

## 2. Windows 使用

将 `hw_tool-0.5.0.zip` 解压到稳定目录，例如：

```text
C:\tools\hw_tool\0.5.0\hw_tool\
```

在 PowerShell 中将 `bin` 加入当前用户 PATH：

```powershell
cd C:\tools\hw_tool\0.5.0\hw_tool
.\publish\windows\install_path.ps1 -HwToolRoot $PWD.Path
```

重新打开 PowerShell 或 VS Code Terminal 后使用：

```powershell
hw_tool.cmd --version
hw_tool.cmd list --tools
hw_tool.cmd csr_tool --help
```

只在当前 PowerShell 生效时增加 `-CurrentSessionOnly`。升级或回退时保留各版本目录，只切换 PATH 指向。

## 3. Linux module load 使用

### 3.1 准备环境

Ubuntu/WSL 示例：

```bash
sudo apt-get update
sudo apt-get install -y environment-modules python3-venv unzip
source /usr/share/modules/init/bash
```

已有 Lmod 或 Environment Modules 的服务器不需要重复安装。

### 3.2 安装发布包

以下示例对应默认安装根目录 `/tools/hw_tool`：

```bash
sudo mkdir -p /tools/hw_tool/0.5.0
sudo unzip -n hw_tool-0.5.0.zip -d /tools/hw_tool/0.5.0

sudo mkdir -p /tools/modulefiles/hw_tool
sudo cp /tools/hw_tool/0.5.0/modulefiles/hw_tool/0.5.0 \
    /tools/modulefiles/hw_tool/0.5.0
```

每个版本使用独立目录，不覆盖旧版本。ZIP 已保存 Linux 启动脚本的执行权限和 LF 换行。

### 3.3 加载和使用

```bash
module use /tools/modulefiles
module avail hw_tool
module load hw_tool/0.5.0

hw_tool --version
hw_tool list --tools
hw_tool csr_tool --help
```

切换和卸载版本：

```bash
module switch hw_tool/0.4.0 hw_tool/0.5.0
module unload hw_tool/0.5.0
```

若使用公共 venv，可在调用前设置：

```bash
export PYTHON=/tools/python/hw_tool/bin/python
```

启动器优先使用 `PYTHON`，未设置时使用 `python3`。

## 4. VS Code 使用

安装统一发布生成的插件：

```bash
code --install-extension dmg-hw-tool-0.5.0.vsix --force
```

也可以在 VS Code Extensions 页面选择 `Install from VSIX...`。插件已经内置 `hw_tool` 和各工具源码，不要求系统 PATH 中存在 `hw_tool`，但仍依赖系统 Python。

需要指定 Python 路径时，在 VS Code 设置中填写：

```json
{
    "dmgHwTool.pythonPath": "python"
}
```

安装后可以从命令面板执行 `HW Tool: Open Tool Documentation...`，查看并调用各工具。详细命令见 [VS Code 插件说明](publish/vscode/README.md)。

## 5. 发布校验

### 5.1 完整产物校验

发布完成或交付前执行：

```bash
python -B hw_tool/publish/verify_release.py \
    hw_tool/publish/out/hw_tool-0.5.0
```

该命令检查：

- `SHA256SUMS` 与文件增删、内容变化；
- 源码包、modulefile 和 VSIX 的版本一致性；
- ZIP 与 VSIX 中的 Python runtime 是否一致；
- Git commit/tag/branch/dirty 等来源信息；
- Linux 启动脚本的执行权限和 LF 换行。

解压并安装后，也可以只校验 `hw_tool/`：

```bash
python -B /installed/hw_tool/publish/verify_release.py /installed/hw_tool
```

校验失败返回非零。`SHA256SUMS` 可以发现拷贝损坏或普通修改，但不是数字签名；需要防止恶意篡改时，应配合只读制品库或独立签名。

### 5.2 发布回归

发布脚本基础回归：

```bash
python -B -m unittest discover -s hw_tool/test -p "test_*release.py"
```

Linux/WSL 可使用 [test_release.sh](publish/linux/test_release.sh) 对两个测试版本执行 `module load/switch/unload`、Python 依赖、全部注册工具 smoke 以及安装后校验。

## 6. 相关文档

- [发布脚本与参数](publish/README.md)
- [Windows PATH 说明](publish/windows/README.md)
- [Linux module load 说明](publish/linux/README.md)
- [VS Code 插件说明](publish/vscode/README.md)
