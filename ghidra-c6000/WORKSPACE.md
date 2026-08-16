# 工作区说明

本项目的工作分在两个目录:

## 1. 分析工作区(原始逆向现场)

```
C:\Users\29517\Documents\ChatGPT\b1on-firmware-reverse
├── analysis\          固件分块、dis6x 反汇编文本、ZDL ELF
├── docs\              早期手工分析报告(注入、ZDL、深度报告)
├── scripts\           注入/解析/校验脚本(37 个)
├── firmware\          固件与 FS 镜像
├── dist\              双设备成品固件
├── probes\            实机探针
└── work\c6000-sleigh\ 本模块的开发现场
    ├── gen\           生成器源码(语料驱动)
    ├── lang\          slaspec/ldefs/cspec/pspec + 已编译 .sla
    ├── image\         重建镜像、insn_map、call_targets、manifest
    ├── ghidra_scripts\ Ghidra 无头脚本
    └── decompiled\     反编译 C 输出
```

## 2. 交付仓库(本仓库)

```
C:\Users\29517\Documents\ChatGPT\ghidra-c6000
├── processor\         可直接安装的 Ghidra 处理器模块
├── tools\             生成器 + Ghidra 脚本(与工作区同步)
├── findings\          逆向发现文档
├── examples\          反编译示例
└── scripts\           一键重建
```

规则:开发迭代在工作区 `work/c6000-sleigh` 中进行;成果(模块、
脚本、文档)定期同步到本仓库并提交。固件本体与厂商代码不进入仓库。
