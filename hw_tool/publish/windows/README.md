# Windows 发布

将 `build_release.py` 生成的 `hw_tool/` 目录保留在任意稳定目录后，在 PowerShell 执行：

```powershell
.\publish\windows\install_path.ps1
```

仅让当前 PowerShell 会话生效：

```powershell
.\publish\windows\install_path.ps1 -CurrentSessionOnly
```

重新打开终端后验证：

```powershell
hw_tool.cmd --version
hw_tool.cmd list
```
