# Zoom B1on/G1on ZDL 格式逆向结论

证据来源:B1on 1.30 / G1on 1.21 原厂固件、B1on 原厂 B1SVT/DELAY、MS-70CDR
原厂语料、自定义 GAIN(实机可用)与各版本 AmpNeve 的逐字节转储与 dis6x
反汇编。完整现场记录见 docs/B1ON_ZDL_REVERSE_PROGRESS.md 与
docs/re_REPORT.md。

## 1. ZDL 容器层

```
00..03  NULL (4B)
04..07  "SIZE"
08..11  payload = 8
12..15  header_size(56 标准 / 232 BCAB / 312 CABI)
16..19  elf_size
20..23  "INFO"
24..27  info_size = 48
28..75  INFO payload(48B):
        32B  version "ZOOM EFFECT DLL SYSTEM VER 1.00"(加载器不校验内容)
        +1   real_type(1 DYN,2 FLT,3 DRV,4 AMP,5 BASSAMP,6 MOD,
                      7 SFX,8 DLY,9 REV,11 PDL,20 BASSDRV,22 BASSPRE)
        +1   unknown1(GAIN=1;B1SVT=0)
        +1   knob_type(0 旋钮)
        +1   unknown2(全 0)
        +1   sort_index(菜单排序)
        +1   sort_sub
        +1   bass_flags(B1on 贝斯箱头 0x10)
        +1   sort_fx_type
        +8B  fx_version "1.00"
76..    ELF(BCAB/CABI 效果在 INFO 与 ELF 之间有额外载荷)
```

要点:

- SIZE 块结构必须正确(长度/偏移),加载器按它切块。
- 版本字符串不被校验,可随意。
- AMP 类(B1on BassAmp / G1on Amp)额外需要 BCAB(176B)/CABI(312B)
  载荷,否则 G1on AMP 分类加载失败;B1on 上非 AMP 分类不需要。

## 2. ELF 层

- TI C6740 EABI、ET_DYN、little-endian、e_flags=0。
- 原厂 36 段 TI 标准布局;自定义工具链 13 段精简布局,B1on 可接受
  (GAIN 实机证明)。
- 关键段索引(原厂约定):`.audio`=3、`.text`=4、`.const`=13、
  `.fardata`=18、`.symtab`=28、`.dynsym`=29、`.dynamic`=30、
  `.dynstr`=31、`.hash`=32、`.strtab`=34、`.shstrtab`=35。
- PT_LOAD:text(r-x@0)/const(r--@0x80000000)/fardata(rw)/PT_DYNAMIC。
- 原厂 `.audio` 为空 NOBITS,代码在 `.text`;我们的 `.audio` 放音频函数。
- `.fardata` 原厂极小(24-48B);自定义模块必须为 0(可写静态会死机)。
- 动态表解析、RELA 重定位、`Dll_<Name>`/`SonicStomp` 符号解析与
  MS-70CDR 加载器逐指令同构(0xc0080bf0 链 vs 0xc00a6b68 链)。

## 3. Dll 入口

- `e_entry` = Dll 地址。
- 3 字段即可:B 跳转后写 `ctx[0]=count`、`ctx[1]=描述符 VA`、
  `ctx[2]=imageInfo VA`,返回。
- 原厂 B1SVT 的 Dll 是 3 字段 + RTS 帮助函数体;DELAY 额外写
  `ctx[4]=0x40`、`ctx[5]=Time_edit 地址`(tap 相关,非加载必需)。
- G1on 上若做 AMP 效果,建议两个额外字段指向 NOP_RETURN stub(见
  ampneve/zdl/README.md 的 G1on 注意事项)。

## 4. SonicStomp 描述符(48B/行)

| 行 | 内容 |
|---|---|
| 行 0 OnOff | max=1 def=0,h=onf handler,fl=0 |
| 行 1 self | max=0xFFFFFFFF pedal=1,h=init,a=audio,**+0x28 = w28 浮点** |
| 用户参数行 | name/max/def/pedal/h(edit)/w28=0/fl |
| 末行哨兵 | fl=0x04(或 0x14,可踏板分配) |

- w28 = DSP 成本声明:SVT=67.47、DELAY=15.55、GAIN=20.0、HALL=27.45、
  ZNR=12.90。
- 预算:B1on 上限 210.0f(0xc00989e4),MS-70CDR 226.0f;超限即失败/卡引导。
- 行数 = Dll count = 2 + 用户参数数(+2 若 AMP CAB/OUT 行)。
- Dll 额外字段(DELAY [4]=0x40 [5]=0x154;HALL [4]=0x26c)= tapmute/
  time_edit 偏移,与状态区无关。

## 5. imageInfo(212B)

- 头:0,1,0,128,64,picVA,h6,h7,count,坐标块 x N。
- 坐标块:kid,x,y,knobInfoVA。
- B1on 原厂固定 count=3 坐标 3(与实际参数数无关,原厂 SVT 9 参数也是 3);
  MS-70CDR 风格 count=9 也能加载,但 B1on 上的旋钮/翻页遍历会错位。

## 6. 运行时 ABI(ctx)

| ctx 槽 | 语义(已验证) |
|---|---|
| ctx[0] | Dll count |
| ctx[1] | 参数表指针(params[0]=ON,params[1..]=旋钮值) |
| ctx[2] | 小状态区指针(滤波等小状态;DELAY 用 +0x10,52B) |
| ctx[3] | 状态区描述符 {base,end,span}:基址、上界、长度 |
| ctx[5] | fx 输入缓冲 |
| ctx[6] | 输出累加缓冲 |
| ctx[11] | 目标指针 magic shuttle(*dst=*src) |
| ctx[12] | 源指针 magic shuttle |

原厂 DELAY/HALL/ROOM/PLATE/AIR/RVRSDLY/HPS/PTCHSHFT/SEQFLTR/B_ATWAH
均使用 ctx[3](反汇编全量确认)。

## 7. B1on 状态区与效果注册表(1.30)

- 每槽固定 1KB 状态区:0x1180f000 + slot*0x400(0xc00939c4/0xc007d760 清零)。
- 自定义效果写 ≥1KB 即死机 = 越界(OTT 80B 能跑与此吻合)。
- 固件启动时从 FS(FLST_SEQ.ZDT + ZDL INFO)构建注册表:
  - 0xc003f200 + effect*28:每效果 28B 元数据(含 real_type 等)
  - 0xc003f290 / 0xc003f2a8 / 0xc003f2c0 / 0xc003f2d8 / 0xc003f2e0:索引表
  - 0xc003fae8 + effect*13:13B 文件名记录
  - 0xc00407e8 + effect*220:220B/效果记录
  - 0xc0042ae8 + effect*16、0xc0042f48 + effect*4
  - 0xc003f204 + slot*28 -> 基址 + effect*48:48B/效果记录(含 word3 上限值)
- MS-70CDR 固件不引用 0xc003f2xx(FS 布局不同)。
- 槽激活代码 0xc0098b98 用注册表记录做类型/上限检查,并写每槽记录
  (0x11814e20 + 44*slot)。

## 8. 剩余未知与探针

唯一未静态确定:B1on 槽激活时用哪个字段决定 ctx[3] 是 1KB 还是原厂
DELAY 的 ~700KB。候选:注册表 48B 记录、每槽记录、w28、real_type。

实验方案(probes/b1on_probe/):13 个只读探针,只读 ctx[3][0..2],在
`end-base >= 阈值` 时用左右声道 wobble 报告;一次刷一个,判读表见
docs/HARDWARE_TEST.md。备选路径:用 ZEM 从 B1on 导出完整 FS,直接读每
效果的 48B/220B 注册表记录,对照自定义 vs 原厂。
