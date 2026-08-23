# Linux module load 发布

按版本部署 `build_release.py` 生成的独立目录：

```text
/tools/hw_tool/0.1.0/hw_tool/
```

将 `modulefiles/hw_tool/0.1.0` 安装到管理员维护的 modulefile 根目录，并按实际部署路径修改其中的 `root`。用户使用：

```bash
module use /tools/modulefiles
module load hw_tool/0.1.0
hw_tool --version
hw_tool list
```
