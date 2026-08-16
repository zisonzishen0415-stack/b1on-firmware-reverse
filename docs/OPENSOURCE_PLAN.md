# 开源计划(已确认)

> 决定(2026-08-16,用户确认):把 C6000 解析与逆向过程"固定化"并开源分享。

## 背景

全网不存在可用的 TMS320C6000 Ghidra 处理器模块(Sleigh 语言定义)。
本项目通过"dis6x 语料驱动 + GNU binutils 指令表参考"的方式自建了
C6000 反编译链路。这套过程本身可复用、值得开源。

## 开源范围(两层)

### 1. 工具与方法层(优先开源)

- `dis6x` 输出 → 结构化 IR 的解析器(`parse_dis.py`)
- 助记符语义表 → Sleigh p-code 生成器(`semantics.py`)
- Sleigh 处理器模块生成器(`gen_sleigh.py`)
- 16 位 compact 指令 → 32 位规范编码的重建器
- 与 `dis6x` 逐条对拍的校验工具
- 取指包格式、C6000 ABI、寄存器约定等逆向笔记

这一层与 Zoom 固件无关,可独立复用于任意 C6000/C674x 固件。

### 2. 处理器模块层

- 生成的 `TMS320C6000` Sleigh 模块(32 位真实编码 + compact 规范解码)
- 仓库形态建议:`c6000-ghidra`(模块 + 生成器 + 校验)

## 边界与许可注意

- **固件本体与反编译出的 Zoom 代码不分发**(厂商 IP);只共享工具、模块与报告。
- binutils 的 tic6x 表格为 GPL 派生:生成器不把其字段表原样打包进开源仓库,
  自建语义表 + 公开生成逻辑;或整体采用 GPL。
- 建议先跑通管道并出可验证的反编译结果,再固化打包。

## 参考

- `repeat98/ZoomMultistompZDL`(ZDL 构建链,缺 Ghidra 反编译这条链)
- 本仓库 `docs/DEEP_RE_B1ON_G1ON.md`、`docs/B1ON_FIRMWARE_REPORT.md`
