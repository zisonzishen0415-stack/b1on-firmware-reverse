# B1on ZDL 逆向报告（2026-08-14）

基于对 B1SVT.ZDL（原厂贝斯箱头）、B1Xon_DELAY.ZDL（原厂延迟）、
GAIN.ZDL（自定义但 B1on 完全可用）、以及我们各版本 AmpNeve 的逐字节
转储与 dis6x 反汇编。

## 1. ZDL 包装层

```
00..03  NULL (4B)
04..07  "SIZE"
08..11  payload=8
12..15  header_size（56 标准 / 232 BCAB / 312 CABI）
16..19  elf_size
20..23  "INFO"
24..27  info_size=48
28..75  INFO payload：
        32B  version "ZOOM EFFECT DLL SYSTEM VER 1.00"
        +1 real_type（1 DYN,2 FLT,3 DRV,4 AMP,5 BASSAMP,6 MOD,
                     7 SFX,8 DLY,9 REV,11 PDL,20 BASSDRV,22 BASSPRE）
        +1 unknown1（GAIN=1；B1SVT=0）
        +1 knob_type（0 旋钮）
        +1 unknown2（全 0）
        +1 sort_index（菜单排序）
        +1 sort_sub
        +1 bass_flags（B1on 贝斯箱头 0x10）
        +1 sort_fx_type
        +8B fx_version "1.00"
76..   ELF（BCAB/CABI 效果在 INFO 和 ELF 之间有额外载荷）
```

## 2. ELF 层

- TI C6740 EABI，ET_DYN，little-endian，e_flags=0。
- 原厂：36 段 TI 标准布局；自定义工具链：13 段精简布局（B1on 可接受，
  GAIN 证明）。
- 关键段索引（原厂约定）：.audio=3、.text=4、.const=13、.fardata=18、
  .symtab=28、.dynsym=29、.dynamic=30、.dynstr=31、.hash=32、
  .strtab=34、.shstrtab=35。
- PT_LOAD：text(r-x@0) / const(r--@0x80000000) / fardata(rw) /
  PT_DYNAMIC。
- .audio 段原厂是空 NOBITS；代码在 .text。
- .fardata 原厂极小（24-48B）。

## 3. Dll 入口

- e_entry = Dll 地址。
- GAIN（可用）：BNOP B3,1 | MVK count=4 → 写 ctx[0]=count、
  ctx[1]=描述符 VA、ctx[2]=imageInfo VA → 返回（3 字段）。
- 我们与 ToTape9 的 Dll：同一 3 字段形状（已逐字节比对一致）。
- B1SVT：3 字段 + 后续 RTS 帮助函数体；DELAY：额外写 ctx[4]=0x40、
  ctx[5]=Time_edit 地址（tap 相关，非加载必需）。
- **结论：3 字段 Dll 在 B1on 可用（GAIN 证明）。**

## 4. 描述符表（0x30/行）

- 行 0 OnOff：max=1 def=0，h=onf handler，fl=0。
- 行 1 self：max=0xFFFFFFFF pedal=1，h=init，a=audio，
  **+0x28 w28 浮点**（SVT=67.47、DELAY=15.55、GAIN=20.0、
  HALL=27.45、ZNR=12.90）。
- 用户参数行：name/max/def/pedal/h(edit)/w28=0/fl。
- 最后一行哨兵：fl=0x04，或 0x14（可踏板分配，pedal=max）。
- 行数 = Dll count = 2 + 用户参数数（+2 若 AMP CAB/OUT 行）。
- w28 高度疑似"状态区大小/开销声明"：自定义效果统一写 20.0，
  而状态大的原厂效果值更大（SVT 67.47）。把 w28 调到 67/127 曾
  卡引导——可能与我们的 ctx[3] 误用叠加，不能据此判定 w28 无作用。

## 5. imageInfo（212B）

- 头：0,1,0,128,64,picVA，h6,h7,count,坐标块×N。
- GAIN(2knob)：count=2 坐标 2；ToTape9/TEcho4(9knob)：count=9 坐标 9。
- B1on 原厂：count=3 坐标 3（无论真实参数数）。
- 坐标块：kid,x,y,knobInfoVA。

## 6. 音频函数 ctx 用法

### GAIN（B1on 完全可用，无状态）
```
ctx[1] = 参数表：params[0]=开关，params[5]=第1旋钮
ctx[5] = fx 输入缓冲；ctx[6] = 输出累加缓冲
ctx[11]→指针→目标；ctx[12]=源；*dst=*src（magic shuttle）
完全不碰 ctx[2]/ctx[3]
```

### B1SVT 共享引擎 KawaOD（原厂可用）
```
ctx[1]=参数；ctx[2]=状态指针（滚动访问）
ctx[5]=输入；ctx[11]/ctx[12]=magic
不碰 ctx[3]
```

### B1Xon DELAY（原厂可用，大状态）
```
ctx[1]=参数；ctx[2]+0x10=小状态块（滤波等，52B）
ctx[3]=描述符 {base,end,span}：base=缓冲基址、end=上界、
        span=长度（做边界检查与回绕）
ctx[5]=输入；ctx[11]/ctx[12]=magic
```

## 7. 我们的问题定位

已确认：
- 无状态探针（同 GAIN 模式）→ B1on 完全可用（UI/旋钮/声音）。
- ctx[3] base/end/span 模型本身没错（DELAY 同款），但我们的
  有状态版本：34KB=静默 bypass（检查失败，不写）、10KB=卡引导、
  .fardata 10KB=卡引导。
- OTT（80B 状态）默认能响但调旋钮失效；ToTape9/Reverson（大状态）
  只能加载或调参崩溃。

待定（需要 smoke 实验区分）：
- 卡引导发生在"音频函数开机执行"阶段还是"文件注册"阶段。
- 若是音频执行：是状态区写入、还是 DSP 处理（除法/IR 循环）导致。

## 8. 关键差异汇总（我们 vs GAIN）

| 项 | GAIN（可用） | 我们 |
|---|---|---|
| ELF | 13 段精简 | 13 段精简（同构） |
| Dll | 3 字段 | 3 字段（一致） |
| 描述符 | 4 行 | 6 行（4knob） |
| imageInfo | count=2 | count=4 |
| 音频状态 | 无 | 10KB ctx[3]/fardata |
| w28 | 20.0 | 20.0 |

**唯一结构性差异：我们写状态，GAIN 不写。**
