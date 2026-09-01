# Linux module load 发布

按版本部署 `build_release.py` 生成的独立目录：

```text
/tools/hw_tool/0.1.0/hw_tool/
```

构建结果会包含与 `--version` 同名的 modulefile，不需要用 `sed` 替换模板版本。安装源码和 modulefile：

```bash
python3 -B hw_tool/publish/build_release.py --version 1.1.1 --no-archive
sudo mkdir -p /tools/hw_tool/1.1.1 /tools/modulefiles/hw_tool
sudo cp -a hw_tool/publish/out/hw_tool-1.1.1/hw_tool /tools/hw_tool/1.1.1/
sudo cp hw_tool/publish/out/hw_tool-1.1.1/modulefiles/hw_tool/1.1.1 /tools/modulefiles/hw_tool/1.1.1
```

用户使用：

```bash
module use /tools/modulefiles
module load hw_tool/1.1.1
hw_tool --version
hw_tool list
```
