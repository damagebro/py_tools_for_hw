# 目录

* [HW Tool 概览](README.md)

## 入门与使用入口

* [VS Code 插件](hw_tool/publish/vscode/README.md)
* [HW Tool 命令行](hw_tool/README.md)

## RTL 开发工具

* [CSR 寄存器生成](csr_tool/README.md)
  * [寄存器定义填写规范](csr_tool/doc/reg_template.md)
* [SRAM 集成](mem_tool/README.md)
* [RTL 例化](gen_rtl_inst/README.md)
* [RTL 空壳与端口交换](gen_rtl_dummy/README.md)
* [RTL 代码片段与 Common IP](py_rtl_snippet/README.md)

## 仿真与验证

* [TB 环境生成](py_rtl_sim/gen_tb_demo/README.md)
* [AXI VIP](py_rtl_sim/sim_axi_vip/README.md)
* [APB VIP](py_rtl_sim/sim_apb_vip/README.md)
* [AHB VIP](py_rtl_sim/sim_ahb_vip/README.md)

## 工程与文档管理

* [RTL Filelist 管理](rtl_flist_mgr/README.md)
  * [SoC、CPU 与 NPU 使用示例](rtl_flist_mgr/test/examples/soc_cpu_npu/README.md)
* [多 Git 仓库管理](git_repo_mgr/README.md)
* [Markdown 转 HTML](py_md2html/README.md)

## 工具集成与发布

* [DE 工具注册](hw_tool/hw_tool_de/README.md)
* [三平台发布操作指南](hw_tool/hw_tool_release_guide.md)
* [发布构建](hw_tool/publish/README.md)
  * [Windows 发布](hw_tool/publish/windows/README.md)
  * [Linux Module 发布](hw_tool/publish/linux/README.md)

## 维护附录

* [Memory 仿真模板](mem_tool/templates/py_sim/README.md)
* [GitBook 维护与接入](doc/gitbook_guide.md)
