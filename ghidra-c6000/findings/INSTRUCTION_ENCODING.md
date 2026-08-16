# C6000 指令编码与取指包笔记

## 取指包结构(C64x+ compact 模式)

- 取指包固定 **32 字节对齐**(8×32 位槽)。
- 若包的第 8 个字(偏移 28)高 4 位为 `0xe`,则该字是**包头**:
  - bits[31:28] = 0xE(签名)
  - bits[27:21] = word_compact[6:0](槽 0-6 是否为 16 位紧凑指令)
  - bits[20] = prot,bits[19] = rs,bits[18:16] = dsz
  - bits[15] = br,bits[14] = sat,bits[13:0] = p 位
- 非包头包:8 个 32 位指令。
- 紧凑槽:两个 16 位指令;16 位指令的真实解码还依赖包头里的
  `sat/br/dsz` 位(会拼进 16 位字),因此**不能脱离包头做上下文无关解码**。

## 本项目采用的解码策略

1. **32 位指令**:保留真实编码;构造器模式忽略 p 位(bits 1-31)。
2. **16 位指令**:在重建镜像中替换为合成 16 位字,合成字与所有真实
   32 位字的低 16 位(掩码后)不相交,保证任意地址解码唯一。
3. **包头**:按真实包头字生成精确 32 位构造器(空语义),让线性扫描
   跨包前进,同时不会与 16 位指令槽冲突。
4. **数据空洞**:分支可达但无可解码指令的地址,补精确 NOP 构造器,
   避免反编译器"bad instruction data"截断。

## 寄存器对

TI 语法 `A5:A4` = 高字 `A5` + 低字 `A4`(小端)。
本项目不定义重叠的 64 位寄存器,而是用局部变量拼/拆:

```sleigh
# 读对
local a:8 = (zext(A5) << 32) | zext(A4);
# 写对
local sp:8 = ...;
local sph:8 = sp >> 32;
A4 = sp:4;
A5 = sph:4;
```

注意:这种建模在 Ghidra 反编译器里对"输出对与输入重叠"的函数
(如 `MPYLI A0,A11,A1:A0`)可能触发 `Overlapping input varnodes`,
见 `KNOWN_LIMITATIONS.md`。

## 关键指令语义

- `BNOP target,5`:分支 + 5 个 NOP 延迟槽(按无条件/条件 goto 建模)。
- `B.S2 B3` / `BNOP.S2 B3,5`:返回,建模为 `return [B3]`。
- `B IRP/NRP`:中断返回,建模为 `return [IRP/NRP]`。
- `CALLP target,retreg`:`retreg = inst_next; call target;`
- `SPLOOP/SPKERNEL/SPMASK`:软流水指令,按 NOP 处理(循环体自然流动)。
