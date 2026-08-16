> **项目状态（2026-08-16 修订）：失败。**
> 经 G1on 实机多次验证，自制 ZDL **无法在 G1on 上稳定工作**（表现为：无 UI、bypass、或切换死机）。
> 此前文档中的“已验证 / 可用 / 可运行 / 已对齐 / 可收口”等表述，均不代表 G1on 实机可用。
> 本项目的 ZDL 目标当前**未达成**，现状为失败；任何后续结论不得以“G1on 可用”为前提。

# Zoom B1on/G1on 固件逆向与 ZDL 自定义效果模块

> 目标:逆向 Zoom B1on/G1on(以及同架构的 MS 系列)固件,掌握 ZDL
> 效果模块的封装、ELF、加载器与运行时 ABI,实现**自己编写并打包 ZDL
> 效果模块**,加载进 B1on / B1Xon / G1on / G1Xon。

**总报告**:`docs/B1ON_FIRMWARE_REPORT.md`(全部逆向成果的一站式汇总)。
**深度报告**:`docs/DEEP_RE_B1ON_G1ON.md`(ABI、槽激活、状态区、FS 等)。

## 当前状态(2026-08)

### 已达成（仅限工具链与静态逆向；ZDL 实机目标失败）

- **ZDL 打包能力（构建/注入管线自检通过，G1on 实机失败）**:`ampneve/` 项目能用 TI cl6x 工具链
  构建出自定义音箱模拟效果并打包为 ZDL(`AmpNeve*.ZDL`),固件注入 +
  菜单登记全流程自检通过(OS 区逐字节不变、全部 ZDL 可解析、哈希一致)；但自制 ZDL 在 G1on 实机均无法稳定工作（无 UI、bypass 或切换死机），项目目标未达成。
- **Ghidra C6000 处理器模块(自建,全网首个)**:见 `ghidra-c6000/`
  (独立交付仓库,本目录为同步副本)。112,233 条固件指令与 TI dis6x
  逐条对齐;关键函数已反编译为可读 C(记录查找、槽处理器表安装、
  效果分发器、槽激活链)。
- **ZDL 格式与运行时 ABI 解析**:INFO 布局、导出符号、ctx 槽语义、
  8 样本/声道音频回调、magic shuttle、状态区/延迟缓冲分配规则。
- **固件结构解析**:Updater FS(4096B 块)、`FLST_SEQ.ZDT` 菜单、
  B1on/G1on 差异(OS 镜像逐字节一致,仅 FS 不同)。

### 已知限制

- `c0098b98`(槽激活)、`c00989e4`(预算检查)、`c0098784`(槽激活链)
  三个函数无法被 Ghidra 干净反编译:固件代码区嵌有数据表,反编译器
  流分析会越界。函数**内容**已通过反汇编与部分反编译确认并记录
  (见 `ghidra-c6000/findings/`)。手工分析结论作为最终交付。

## 仓库结构

```
ampneve/                可构建的自定义效果项目(AmpNeve 音箱模拟)
  zdl/build.py          ZDL 构建入口(cl6x 编译 -> 安全审计 -> 链接 -> 打包)
  zdl/manifest.json     9 旋钮 G1on AMP 配置(默认)
  zdl/manifest_hw4.json B1on 4 旋钮硬件配置
  core/                 DSP 核心(与 VST3 共用同一份 C 代码)
  dist/                 构建产物:AmpNeve.ZDL / AmpNeve_B1on.ZDL / ...
  dist_smoke/           smoke(直连)测试模块,新设备第一刷用这个
probes/b1on_probe/      ctx[3] 状态区大小决定性实验、13 个只读探针
firmware/               原厂固件(Zoom 官方 Updater 原始文件,不分发)
stock_zdl/B1on_v1.30/   从 B1on 1.30 固件解出的原厂效果语料(约 120 个 ZDL+RAW)
analysis/               反汇编与 ELF 语料
  b1on_os/              B1on 固件关键地址块反汇编(chunk_*.dis)
  ctx_class/            原厂 ZDL 解包后的 ELF 反汇编
  zdl_elfs/             自建/原厂 ZDL 的 ELF 与反汇编
docs/                   全部逆向报告与注入文档
scripts/                解析/注入/校验工具(37 个)
ghidra-c6000/           Ghidra C6000 模块 + 工具链 + 发现文档(同步副本)
dist/                   双设备成品固件(含注入效果,不分发)
third_party/            第三方参考代码(不分发)
work/                   开发现场与中间产物(不分发)
```

## 快速开始:打包一个自定义效果 ZDL

```powershell
# 1. 编写 DSP(见 ampneve/core/ampsim.c 的示例)
# 2. 构建 ZDL
python ampneve/zdl/build.py
# 3. 产物在 ampneve/dist/AmpNeve.ZDL
# 4. 注入固件
python scripts/zfe_inject.py --help
```

自定义 DSP 安全规则:保持 `memsz == filesz`、`.fardata` 极小、
不使用 C 运行时启动、不引入 DSBT/GOT/TLS、音频回调不依赖 B14(DP)。

## 使用 Ghidra 模块分析固件

```powershell
# 安装模块:把 ghidra-c6000/processor/TMS320C6000 复制到
# Ghidra/Processors/ 下(需保留 Module.manifest)

# 全量反汇编(清单驱动,与 dis6x 对齐)
analyzeHeadless <proj> <name> -import fw_b1on_all.out `
    -processor TMS320C6000:LE:32:default `
    -postScript FullDis.java insn_map.txt call_targets.txt

# 批量反编译
analyzeHeadless <proj> <name> -process fw_b1on_all.out `
    -postScript DecompileFns.java <outdir> c008940c c00bada8 ...
```

详细说明见 `ghidra-c6000/README.md` 与 `ghidra-c6000/tools/README.md`。

## 关键文档索引

- `docs/B1ON_FIRMWARE_REPORT.md` — 总报告
- `docs/DEEP_RE_B1ON_G1ON.md` — 深度逆向(ABI/槽激活/状态区/FS)
- `docs/FIRMWARE_INJECTION.md` — 固件注入流程
- `docs/USER_GUIDE.md` — 用户手册(刷机)
- `ghidra-c6000/findings/B1ON_G1ON_RE.md` — 反编译交叉验证的发现
- `ghidra-c6000/findings/ZDL_FORMAT.md` — ZDL 封装/INFO/导出符号
- `ghidra-c6000/findings/KNOWN_LIMITATIONS.md` — 已知限制与修复方向

## 许可与分发边界

- 本仓库代码(脚本、工具、自定义效果源码)以 MIT 许可发布(见各子目录
  LICENSE / `ghidra-c6000/LICENSE`)。
- **固件本体、原厂 ZDL、成品固件镜像不分发**(Zoom 厂商 IP):
  `firmware/`、`dist/`、`stock_zdl/`、`third_party/`、`work/` 被
  `.gitignore` 排除。
- 反汇编文本(`analysis/*.dis`)作为研究语料保留;GNU binutils 表格
  仅作参考(GPL 派生),不随工具链打包。
