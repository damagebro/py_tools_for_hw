# hw_tool 三种发布方式

本文说明 `hw_tool` 在 Windows PATH、Linux `module load` 和 VS Code `.vsix` 三种方式下的构建、部署、验证与升级过程。默认命令均从 `py_tools_for_hw` 仓库根目录执行，示例版本为 `0.4.0`。

## 1. 发布方式概览

| 发布方式          | 主要用户              | 交付产物                                      | 运行依赖                                      |
| ----------------- | --------------------- | --------------------------------------------- | --------------------------------------------- |
| Windows PATH      | Windows 命令行用户    | `hw_tool-<version>.zip` 或解压后的源码目录    | 系统 Python 3.11+ 和工具所需 Python 包        |
| Linux module load | Linux/WSL/服务器用户  | 版本化源码目录和 Tcl modulefile               | Python 3.11+、Environment Modules/Lmod、Git   |
| VS Code `.vsix`   | RTL 编辑器用户        | `dmg-hw-tool-<version>.vsix`                  | VS Code 1.85+、系统 Python 3.11+              |

Windows PATH 与 Linux module load 共用 `build_release.py` 生成的离线源码包。VSIX 会在打包时重新生成同一套独立 runtime，因此安装插件后不要求系统 PATH 中已有 `hw_tool`。

## 2. 发布前准备

### 2.1 仓库来源

构建命令只需在 `py_tools_for_hw` checkout 中运行。`py_tools_for_hw` 工具从当前工作区复制；`mem_tool` 默认根据 `hw_tool_de/src/tool_registry.py` 中登记的 `com` Git URL 临时 clone，不再要求本机存在同级 `com` 仓库。

发布包生成后会把 `mem_tool` 复制进自身的 `repository/com/`，临时 clone 会自动清理，用户端也不需要单独保留 `com` checkout。

### 2.2 固定源码版本

正式发布应从干净的 Git tag 或指定 commit 构建，避免把未确认的本地修改带入发布包。外部 `com` 仓库可通过 `--repo-ref` 指定 branch、tag 或 commit：

```bash
git status --short
git log -1 --oneline
python -B hw_tool/publish/build_release.py --version 1.1.1 --repo-ref com=v1.2.0
```

无网络或需要验证本地修改时，可显式指定本地 checkout；`--repo-path` 的优先级高于 URL：

```bash
python -B hw_tool/publish/build_release.py --version 1.1.1 --repo-path com=path/to/com
```

构建产物中的 `release_info.toml` 会记录各仓库的 URL、ref、实际 commit、来源方式和 dirty 状态。使用 `--repo-path` 时不会切换或修改本地 checkout，ref 记录为 `working-tree`，实际内容由 commit 和 dirty 状态确定。

### 2.3 安装 Python 依赖

Windows 构建机或用户机：

```powershell
python --version
python -m pip install jinja2 openpyxl Markdown
```

Linux 构建机或用户机：

```bash
python3 --version
python3 -m pip install --user jinja2 openpyxl Markdown
```

`csr_tool` 使用 `jinja2/openpyxl`，`md2html` 使用 `Markdown`。仅调用不需要这些包的工具时，可以不安装对应依赖；执行 `hw_tool doctor` 可查看当前缺失项。

### 2.4 发布前检查

```bash
python -B hw_tool/src/hw_tool.py --version
python -B hw_tool/src/hw_tool.py doctor
python -B hw_tool/src/hw_tool.py verify
python -B hw_tool/src/hw_tool.py test --all
```

### 2.5 生成离线源码包

```bash
python -B hw_tool/publish/build_release.py --version 0.4.0
```

生成结果：

```text
hw_tool/publish/out/
├── hw_tool-0.4.0/
│   ├── hw_tool/
│   │   ├── bin/
│   │   ├── src/
│   │   ├── repository/
│   │   └── release_info.toml
│   └── modulefiles/
│       └── hw_tool/
│           └── 0.4.0
└── hw_tool-0.4.0.zip
```

外部仓库较大时可增加 `--shallow`，仅获取所选 ref 对应的浅层历史：

```bash
python -B hw_tool/publish/build_release.py --version 0.4.0 --repo-ref com=main --shallow
```

只生成目录、不生成 zip：

```bash
python -B hw_tool/publish/build_release.py --version 0.4.0 --no-archive
```

指定其他输出根目录：

```bash
python -B hw_tool/publish/build_release.py --version 0.4.0 --output-root path/to/release
```

## 3. Windows PATH 发布

### 3.1 构建机交付

将 `hw_tool/publish/out/hw_tool-0.4.0.zip` 交付给用户，也可以直接交付解压后的 `hw_tool-0.4.0/hw_tool/` 目录。

### 3.2 用户部署

将发布包解压到稳定且不会随意删除的目录，例如：

```text
C:\tools\hw_tool\0.4.0\hw_tool\
```

进入发布目录，在 PowerShell 中永久加入当前用户 PATH：

```powershell
cd C:\tools\hw_tool\0.4.0\hw_tool
.\publish\windows\install_path.ps1 -HwToolRoot $PWD.Path
```

只让当前 PowerShell 会话生效：

```powershell
.\publish\windows\install_path.ps1 -HwToolRoot $PWD.Path -CurrentSessionOnly
```

永久修改 PATH 后需要重新打开 PowerShell 或 VS Code Terminal。

### 3.3 验证

```powershell
Get-Command hw_tool.cmd
hw_tool.cmd --version
hw_tool.cmd doctor
hw_tool.cmd list --tools
hw_tool.cmd csr_tool --help
```

### 3.4 升级与回退

新版本应安装到新的版本目录，再把用户 PATH 中的旧 `hw_tool/bin` 替换为新路径。回退时恢复旧版本路径即可，不要覆盖旧版本目录。

## 4. Linux module load 发布

### 4.1 安装 module 命令

Ubuntu/WSL：

```bash
sudo apt-get update
sudo apt-get install -y environment-modules
source /etc/profile.d/modules.sh
```

RHEL/Rocky Linux：

```bash
sudo dnf install -y environment-modules
source /etc/profile.d/modules.sh
```

已有 Lmod 的服务器无需重复安装。

### 4.2 部署源码目录

在 Linux 构建机执行离线源码包命令后，将版本目录安装到共享工具路径：

```bash
python3 -B hw_tool/publish/build_release.py --version 0.4.0 --no-archive
sudo mkdir -p /tools/hw_tool/0.4.0
sudo cp -a hw_tool/publish/out/hw_tool-0.4.0/hw_tool /tools/hw_tool/0.4.0/
sudo chmod +x /tools/hw_tool/0.4.0/hw_tool/bin/hw_tool
```

### 4.3 安装 modulefile

`build_release.py` 会根据 `--version` 直接生成同名 modulefile。发布 `1.1.1` 时文件名、部署路径和 `HW_TOOL_VERSION` 都会自动使用 `1.1.1`，不需要再执行 `sed`：

```bash
sudo mkdir -p /tools/modulefiles/hw_tool
sudo cp hw_tool/publish/out/hw_tool-0.4.0/modulefiles/hw_tool/0.4.0 /tools/modulefiles/hw_tool/0.4.0
```

生成后的关键内容应为：

```tcl
#%Module
module-whatis "Hardware development tool hub 0.4.0"

set root /tools/hw_tool/0.4.0/hw_tool
prepend-path PATH $root/bin
setenv HW_TOOL_HOME $root
setenv HW_TOOL_VERSION 0.4.0
```

如使用独立 Python venv，可以在 modulefile 中增加：

```tcl
setenv PYTHON /tools/hw_tool/0.4.0/venv/bin/python
```

Linux 启动器会优先使用 `PYTHON`，未设置时使用 `python3`。

如果源码不是部署到默认的 `/tools/hw_tool`，构建时应同步指定安装根目录，生成的 modulefile 会直接写入该路径：

```bash
python3 -B hw_tool/publish/build_release.py --version 1.1.1 --linux-install-root /opt/company/hw_tool
```

### 4.4 用户加载与验证

```bash
source /etc/profile.d/modules.sh
module use /tools/modulefiles
module avail hw_tool
module load hw_tool/0.4.0
module list
hw_tool --version
hw_tool doctor
hw_tool list --tools
hw_tool csr_tool --help
```

退出当前版本：

```bash
module unload hw_tool/0.4.0
```

切换版本：

```bash
module switch hw_tool/0.3.0 hw_tool/0.4.0
```

管理员可把 `/tools/modulefiles` 加入全局 `MODULEPATH`；个人或 WSL 验证环境也可以在 `~/.bashrc` 中初始化 Modules 后执行 `module use /tools/modulefiles`。

## 5. VS Code VSIX 发布

### 5.1 构建机准备

VSIX 构建需要 Python、Node.js 和 npm。当前打包脚本不依赖 `@vscode/vsce`，不需要联网下载 Node 包。

```bash
python --version
node --version
npm --version
```

发布新版本前，需要同步修改 `hw_tool/publish/vscode/package.json` 中的 `version`，并确保 `package` 命令和输出文件名使用相同版本。

### 5.2 一键检查与打包

```bash
cd hw_tool/publish/vscode
npm run package
```

该命令依次执行：

```text
JavaScript 语法检查
→ helper 测试
→ 同步 py_rtl_snippet
→ 生成内置 runtime/hw_tool
→ 打包 VSIX
```

当前版本产物：

```text
hw_tool/publish/vscode/out/dmg-hw-tool-0.4.0.vsix
```

需要分步执行时：

```bash
python -B scripts/sync_resources.py
python -B scripts/sync_runtime.py
node test/test_helpers.js
python -B scripts/pack_vsix.py --output out/dmg-hw-tool-0.4.0.vsix
```

### 5.3 用户安装

命令行安装或覆盖已有版本：

```bash
code --install-extension hw_tool/publish/vscode/out/dmg-hw-tool-0.4.0.vsix --force
```

也可以在 VS Code Extensions 页面选择 `Install from VSIX...`，然后选择生成的文件。

### 5.4 Python 设置与验证

插件内置 `hw_tool` 和已注册工具源码，但不内置 Python。目标机应安装相应依赖，并在 VS Code 设置中配置实际解释器：

```json
{
    "dmgHwTool.pythonPath": "python"
}
```

安装后在命令面板执行：

```text
HW Tool: Open Tool Documentation...
HW Tool: Copy RTL Instance
HW Tool: Create CSR Template...
```

确认 Snippet 可用时，在 Verilog/SystemVerilog 文件中输入 `rtl-module` 或 `rtl-always_dff`。

卸载插件：

```bash
code --uninstall-extension dmg.dmg-hw-tool
```

## 6. 发布检查清单

| 检查项               | Windows PATH | Linux module       | VSIX             |
| -------------------- | ------------ | ------------------ | ---------------- |
| 固定 Git tag/commit  | 必须         | 必须               | 必须             |
| `hw_tool doctor`     | 必须         | 必须               | 建议             |
| `hw_tool test --all` | 构建前       | 构建前             | runtime 同步前   |
| Python 依赖          | 用户机安装   | 用户机或共享 venv  | 用户机安装       |
| PATH/MODULEPATH      | PATH         | MODULEPATH         | 不需要           |
| 独立工具源码         | 已内置       | 已内置             | 已内置           |
| 升级方式             | 切换 PATH    | `module switch`    | 覆盖安装 VSIX    |

三种发布方式都应从同一个 Git tag/commit 构建，并使用相同版本号。Windows/Linux 包中的 `release_info.toml` 与 VSIX 的 `package.json.version` 是离线环境核对版本的主要依据。

## 7. 相关文档

- [hw_tool 发布目录说明](publish/README.md)
- [Windows PATH 发布](publish/windows/README.md)
- [Linux module load 发布](publish/linux/README.md)
- [VS Code 插件发布](publish/vscode/README.md)
- [Linux/WSL/Docker 验证计划](../doc/plan_linux_module_release.md)
