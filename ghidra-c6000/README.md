# Ghidra TMS320C6000 处理器模块与 Zoom 固件逆向

> 自建的全网首个可用 **TMS320C6000 (C64x+/C674x) Ghidra 处理器模块**,
> 以及围绕 Zoom B1on/G1on 固件的源码级逆向发现与工具链。

## 为什么需要这个项目

Ghidra 官方(以及 OpenGhidra 等分支)从未提供 TMS320C6000 的 Sleigh 语言定义。
真实固件使用 C64x+ 的 **compact(16/32 位混合)指令编码**,指令宽度由
32 字节取指包中的包头(签名 `0xe-------`)决定,Ghidra 的线性解码器无法感知,
因此不能直接写一个"普通"的处理器模块导入真实固件。

本项目解决这个问题,并把它变成可复用的工具链:

1. **语料驱动生成**:从 TI `dis6x` 的逐条反汇编输出(权威基准)生成
   Sleigh 构造器——每个真实指令字一个精确模式,32 位指令保留真实编码,
   16 位 compact 指令在重建镜像中替换为与真实编码零冲突的合成模式。
2. **取指包头建模**:每个真实包头字生成精确 32 位构造器,让线性扫描能
   跨包解码,且不会误吞 16 位指令槽。
3. **清单驱动全量反汇编**:按 dis6x 布局(与包对齐)逐条创建指令,
   112,233 条指令 100% 对齐;少数分支指向的数据空洞用 NOP 构造器填平,
   保证控制流可穿过。
4. **Ghidra 反编译器**:补齐 cspec 的 `<global>` 声明后,反编译器可正常
   输出 C 伪代码(已验证:槽激活链、效果分发器、槽处理器表安装、记录查找等)。

## 当前状态

- 全量反汇编:112,233 条指令与 TI `dis6x` 逐条对齐。
- 反编译通过:记录查找 `c008940c`、槽处理器表安装 `c00bea38/c00beac0`、
  效果分发器 `c00bada8`;`c0098784` 有部分输出(见 `examples/`)。
- 反编译受限:`c0098b98`、`c00989e4`(以及干净导入下的 `c0098784`)
  触发 Ghidra 反编译器 `Overlapping input varnodes`(寄存器对建模问题),
  详细分析见 `findings/KNOWN_LIMITATIONS.md`。

## 仓库结构

```
ghidra-c6000/
├── processor/TMS320C6000/       Ghidra 处理器模块(可直接放入
│   └── data/languages/            Ghidra/Processors/ 使用)
│       ├── TMS320C6000.slaspec   语言定义(生成产物,3.7MB)
│       ├── TMS320C6000.sla       已编译语言(1.2MB)
│       ├── TMS320C6000.ldefs     语言注册
│       ├── TMS320C6000.cspec     编译器规格(栈/ABI/全局空间)
│       └── TMS320C6000.pspec     处理器规格(PC/默认内存)
├── tools/
│   ├── gen/                      生成器与解析器
│   │   ├── parse_dis.py          dis6x 输出 → 结构化 IR
│   │   ├── semantics.py          指令 → Sleigh p-code
│   │   ├── gen_sleigh.py         生成 slaspec + 重建镜像 + ELF
│   │   ├── tic6x_tables.py       (参考)GNU binutils tic6x 表解析
│   │   └── validate_decode.py    解码器对拍校验
│   └── ghidra_scripts/           Ghidra 无头脚本
│       ├── FullDis.java          清单驱动全量反汇编
│       ├── DumpDis.java          反汇编转储
│       ├── DecompileFns.java     批量反编译到 C
│       └── RawPcodeDump.java     原始 pcode 检查
├── findings/                     逆向发现文档
├── examples/decompiled/          关键函数反编译 C 示例
└── scripts/build_all.ps1         一键重建(生成→编译→安装)
```

## 快速开始

### 1. 安装模块

把 `processor/TMS320C6000/` 整个目录复制到 Ghidra 安装目录:

```
Ghidra/Processors/TMS320C6000/
```

(目录内需保留 `Module.manifest`;Ghidra 靠它发现处理器模块。)

### 2. 导入固件

用 `tools/ghidra_scripts/FullDis.java` + `insn_map.txt` 导入并全量反汇编:

```
analyzeHeadless <proj> <name> -import fw_b1on_all.out \
    -processor TMS320C6000:LE:32:default \
    -postScript FullDis.java insn_map.txt
```

### 3. 反编译

```
analyzeHeadless <proj> <name> -process fw_b1on_all.out \
    -postScript DecompileFns.java <outdir> c0098784 c00bada8 ...
```

## 许可

代码与文档采用 MIT 许可(见 `LICENSE`)。
注意:

- 本仓库**不含** Zoom 固件本体与反编译出的厂商代码的完整转储;
  示例反编译片段仅用于说明方法。
- `tools/gen/tic6x_tables.py` 仅解析 GNU binutils 的公开指令表结构
  (GPL 派生),生成器本身不使用其字段数据,全部模式来自 TI dis6x 语料。

## 相关资源

- TI `dis6x` / `cl6x` / `ofd6x`(C6000 Code Generation Tools 8.x)
- GNU binutils `tic6x`(解码参考,不用于生成)
- `repeat98/ZoomMultistompZDL`(ZDL 构建链,同平台)
