# 工具链说明

## 生成器(`gen/`)

输入:TI `dis6x` 输出的 `.dis` 文本 + 固件原始 `.bin` 分块。

```bash
python gen_sleigh.py
```

产出:

- `lang/TMS320C6000.slaspec/.ldefs/.cspec/.pspec`
- `image/*.bin`(16 位合成字替换后的重建镜像)
- `image/*.out`(最小 C6000 ELF 封装)
- `image/fw_b1on_all.out`(全部块合成单 ELF)
- `image/insn_map.txt`(指令地址清单,供 FullDis 使用)
- `image/manifest.json`

校验:

```bash
python validate_decode.py   # 用 binutils 表对拍 32 位解码(参考)
```

依赖:Python 3.10+;可选:GNU binutils 2.43 源码(仅 `tic6x_tables.py` 参考)。

## Ghidra 无头脚本(`ghidra_scripts/`)

### FullDis.java —— 清单驱动全量反汇编

```bash
analyzeHeadless <proj> <name> -import fw_b1on_all.out \
    -processor TMS320C6000:LE:32:default \
    -postScript FullDis.java insn_map.txt
```

按 `insn_map.txt` 逐条 `lang.parse` + `createInstruction`,
保证与 dis6x 布局完全一致(包括取指包头伪指令)。

### DecompileFns.java —— 批量反编译

```bash
analyzeHeadless <proj> <name> -process fw_b1on_all.out \
    -postScript DecompileFns.java <outdir> c0098784 c00bada8 ...
```

支持 `地址:长度` 语法(如 `c0098b98:0x24`)限制函数体,便于定位问题。
函数体按连续指令自动计算,并在反编译器打开前建好函数。

### DumpDis.java / RawPcodeDump.java

分别用于转储反汇编文本和检查原始 pcode(输入重叠诊断)。

## 重新生成模块的完整流程

```powershell
# 1. 用 TI dis6x 反汇编固件块
dis6x chunk_c0078d20_4f860.out > c0078d20.dis

# 2. 生成语言 + 重建镜像
python gen_sleigh.py

# 3. 编译 Sleigh
sleigh -a lang

# 4. 安装模块(复制到 Ghidra/Processors/TMS320C6000)

# 5. 导入 + 全量反汇编 + 反编译(见上)
```

`scripts/build_all.ps1` 封装步骤 2-4。
