> **项目状态（2026-08-16 修订）：失败。**
> 经 G1on 实机多次验证，自制 ZDL **无法在 G1on 上稳定工作**（表现为：无 UI、bypass、或切换死机）。
> 此前文档中的“已验证 / 可用 / 可运行 / 已对齐 / 可收口”等表述，均不代表 G1on 实机可用。
> 本项目的 ZDL 目标当前**未达成**，现状为失败；任何后续结论不得以“G1on 可用”为前提。

# B1on / G1on 固件深度逆向报告(2026-08-16)

本轮对 B1on v1.30 与 G1on v1.21 官方 Updater 内的固件镜像做了完整解析,
把上一轮(2026-08-13~15)留下的"ctx[3] 状态区大小由什么字段决定"问题
推进到:静态排除 w28、锁定 real_type 派发机制、并确认两台设备 OS 逐字节
相同。

## 已验证事实 / Verified facts

### 1. B1on v1.30 与 G1on v1.21 的 OS 镜像逐字节相同

两个 Updater 内固件镜像结构完全一致(11 个记录,所有记录 SHA1 相同):

| 记录地址 | 长度 | 内容 |
|---|---|---|
| 0x1180F800 | 0x92A0 | L2 RAM 初始化数据(参数表/模板) |
| 0x11818AA0 | 0x1EA0 | L2 RAM 初始化数据 |
| 0x1181D660 | 0x480 | L2 RAM 初始化数据 |
| 0x1181DAE0 | 0x40C | L2 RAM 初始化数据 |
| 0xC0078D18 | 8 | 引导向量 |
| 0xC0078D20 | 0x4F860 | 主 OS 代码(本仓库 analysis/b1on_os) |
| 0xC00C8580 | 0x13504 | OS 代码/数据续 |
| 0xC00DD72C | 0x900 | 尾部代码 |
| 0xC00DE040 | 0x2A0 | 尾部代码 |
| 0xC00DE400 | 0x200 | 尾部代码 |
| 0xC00DEC6C | 0x17EC | 尾部代码 |

记录格式:`01 59 53 58`("YSX") + 小端 addr(4) + 小端 len(4) + 数据。
镜像之外的地址(如 0xC00DBA84..0xC00DD72C、0xC00DD4F8 附近)是**未初始化
RAM**,启动时为零,由运行时代码填充。

结论:**B1on 与 G1on 的差异只在 FS 分区(ZDL 列表/FLST_SEQ),OS 行为完全
一致**;所有针对 B1on 1.30 的静态结论 1:1 适用于 G1on 1.21。

### 2. 启动注册表(0xC003F200 区,OS RAM)

固件启动时扫描 FS 中的 ZDL,构建多张并行索引表(均为每效果一条):

| 地址 | 步长 | 内容 |
|---|---|---|
| 0xC003F200 + e*28 | 28B | 元数据;**byte0 = real_type-2**(读取器 0xc0089434) |
| 0xC003F204 + e*31 | 31B | word0 = 48B 每槽记录池的基址 |
| 0xC003F208 + e*31 | 31B | 另一个基址表 |
| 0xC003F20C + e*31 | 31B | 另一个基址表 |
| 0xC003F290 + e*4 | 4B | 初始统一指向 0xc00c6810(登记函数) |
| 0xC003F2A8 + e*4 | 4B | 槽位索引值(槽激活时与 4 比较) |
| 0xC003F2C0 + e*4 | 4B | 登记状态 |
| 0xC003F2D8 + e | 1B | 标记字节 |
| 0xC003F2E0 + e | 1B | 标记字节 |
| 0xC00407E8 + e*220 | 220B | 每效果大记录(读取器 0xc00894ac) |
| 0xC0042A44 + ... | 4B | fxid 查找表(0xc00895f4 扫描) |
| 0xC0042AE8 + e*16 | 16B | 每效果记录(读取器 0xc00894aa) |
| 0xC0042EA8 + e*4 | 4B | 索引表 |
| 0xC0042F48 + e*4 | 4B | 索引表 |

**48B 每槽记录**:`[0xC003F204 + 31*effect] + slot*48`(读取器 0xc008940c),
关键字段:

- `+0x1C`(word7)= **效果激活函数指针**(槽激活时被间接调用)
- `+0x28`(word10)= **w28 浮点**(DSP 成本;预算检查读取)

### 3. 每槽运行时记录(OS RAM 0x1181xxxx)

| 地址 | 内容 |
|---|---|
| 0x1180B160 + slot*44 + idx*4 | 每槽每链位记录(激活状态字) |
| 0x1180B23C | 每槽位图(word,按 slot 置位) |
| 0x1180B370 + slot*44(+ idx*4) | 每槽激活状态字 |
| 0x1180BCF4 + ... | 槽占用位图 |
| 0x11814E20 + slot*44 | 每槽记录(上一轮记录) |

状态区(启动清零,每槽两个 1KB):

- 0x11800000 + slot*0x400(计算器 0xc007d760)
- 0x117FF000/0x117FF400 + slot*0x400(双区清零 0xc00939c4、0xc007d768)

自定义效果 ctx[3] 只拿到 1KB/槽,写超即越界死机(与 OTT 80B 可跑吻合)。

### 4. 槽激活链(已全量定位)

```
c0098b98  槽激活入口(每槽记录读写、参数钳制)
  └─ c0098784  分发器(按链位 0/1/2..9 分派)
       ├─ 链位 1: c00ac0cc / c00bb02c / c00a5de0 ...
       ├─ 链位 0: c00a5e84
       └─ 链位 2..9: 读 48B 记录 word7 → B.S2X 间接调用(效果激活函数)
  └─ c0098994 / c00989cc / c0098ad8 / c00989e4  预算检查链
```

效果激活函数(48B word7)负责该效果的 ctx/缓冲初始化——即大状态区分配
发生在这里,而不是槽激活代码本身。

### 5. 预算检查(0xc00989e4)

```
sum = Σ 已激活效果的 w28(48B 记录 +0x28,LDW *A4[10] 是唯一读取点)
    + 表A[0xc00db120][count(记录word0==0x03000000)]
    + 表B[0xc00db138][count(记录word0==0x07000096)]
return sum <= 210.0f   (0x43520000, 0xc0098ac8)
```

成本表内容(0xc00db120,浮点):`[0,0,10,50,50,50,0,0, 0,0,10,60,60,60,...]`

**关键静态证据:w28 浮点在整个 OS 里只在预算检查被读取**(检索 `LDW *A4[10]`
与全部 `ADDSP` 使用点,仅 0xc0098a16 一处)。因此 **w28 不决定状态区大小**,
它是纯成本声明。上一轮探针 C 组(w28=15.55)可据此判为"理论不必要"。

### 6. 与 MS-70CDR 的差异

MS-70CDR(zoomreverse/repeat98 项目已确认):每槽处理器状态在
0x11F03000 + slot*0xD4(212B);自定义效果 ctx[3] 有大区(512KB 下限,
Galactic 528KB、Reverson ~160KB 均在 MS-70CDR 实测可用)。

B1on/G1on 与 MS-70CDR 的 OS 不同(仅加载器逐指令同构),B1on/G1on 给
自定义效果的是固定 1KB/槽。即"1KB 限制"是 B1on/G1on 平台行为,不是
ZDL 字段问题。

## 推断与置信度 / Inference and confidence

| 结论 | 置信度 | 依据 |
|---|---|---|
| B1on/G1on OS 逐字节相同 | 高(已验 SHA1) | 11 记录全部一致 |
| w28 不决定状态区大小 | 高(静态穷举) | 全库唯一浮点读取点在预算检查 |
| 状态区分配由 48B word7 激活函数执行 | 中高 | 槽激活 B.S2X 间接调用,注册表结构完整 |
| 激活函数由 real_type 派发(延迟/混响→大区,其余→1KB) | 中 | 与 DELAY 行为、注册表结构、MS 差异一致;尚未逐指令钉死赋值处 |
| DELAY 大区约 700KB | 中 | 上轮探针阈值设计依据(待实机) |

## 剩余未知 / Remaining unknown

"48B 记录 word7 具体由 loader 的哪条指令、按 real_type 的哪个值安装"尚未
逐指令钉死(加载器在 0xc0080bf0 链与 0xc00884e0 登记簇内,字段赋值分散在
多个分支)。实机探针仍是最终确认手段,且已可收窄:

- **A 组(FLT,w28=20)**:量自定义状态区真实大小(预计 1KB)
- **B 组(real_type=DLY)**:验证 DLY 身份是否拿到大区(**关键组**)
- **C 组(w28=15.55)**:按静态结论**可不刷**;刷了也只是复证

## 补充:状态区机制的最终静态定位(2026-08-16 第二轮)

### 7. ZDL 描述符里没有状态区大小字段(已逐字节验证)

对原厂 DELAY / B1SVT 与我们 GAIN / AmpNeve 的描述符逐行解包:

| 文件 | self 行 w28 | 参数行 +0x18(res) |
|---|---|---|
| DELAY | 15.55 | Time 行 res=0xF9F(3999 = 同步上限),其余 0 |
| B1SVT | 67.47 | 全 0 |
| GAIN | 20.00 | 全 0 |
| AmpNeve | 20.00 | 全 0 |

结论:描述符唯一影响分配的自声明字段是 w28(成本),而 w28 已确认只在
预算检查被读取——**描述符层面不存在"申请大状态区"的途径**。

### 8. INFO 字段全解(B1on/G1on 1.30/1.21)

```
INFO+32  real_type(DELAY=08 DLY / SVT=05 BASSAMP / GAIN=02 FLT / AmpNeve=04 AMP)
INFO+33  unknown1(GAIN/AmpNeve=1;SVT=0)
INFO+34  knob_type=0
INFO+35  unknown2=0
INFO+36  sort_index = fxid(u16 LE)(DELAY=8,SVT=16,GAIN=0x190,AmpNeve=0x1A4)
INFO+38  sort_sub=0
INFO+40  bass_flags(B1SVT=0x10)
INFO+41  sort_fx_type = real_type
INFO+42  fx_version "1.00"
```

### 9. 每槽运行时表(OS RAM)

| 表 | 内容 |
|---|---|
| 0xC00DD4F8 + slot*4 | 每槽 ctx 指针(每块 0x348=840B,启动清零,c00bea38) |
| 0xC00DD510 + slot*4 | 每槽二级状态指针(每块 0x2A0=672B,启动清零) |
| 0xC00DD528 + slot*4 | 每槽处理器指针(初值 0xc00c6840/0xc00c6844;48B word8 经 c00beac0 安装) |
| 0xC00DD588 | 每槽顺序表(写 1..5) |

### 10. 延迟/混响大区 = 外部内存 5×640KB 缓冲

启动时 c00bd2a4 清零 5 块外部缓冲(每块 0xA0000=640KB):

```
slot0: 0xC01A5800   slot1: 0xC0251C40   slot2: 0xC02FE080
slot3: 0xC03AA4C0   slot4: 0xC0456900   (步长 0xAC440)
```

每槽描述表在 **0xC00DF948**(5×{base, 0xAC440}):这就是"原厂 DELAY
~700KB"大区的来源。自定义 FLT/DYN 效果不走这张表,只拿到 1KB L2 槽区
(0x11800000+slot*0x400)。

### 11. 派发链(最终)

```
48B 记录 word7(激活函数) → 效果激活(设置 ctx/缓冲)
48B 记录 word8 → 每槽处理器表 0xC00DD528[slot](c00beac0)
0xC00DD528[slot] → 音频引擎逐块调用(c00bada8 通用分发器,word7/word9)
```

延迟/混响类效果(c00b6fe8/c00b7208 等)激活时引用 0xC00DD4F8[slot] 的
ctx 和外部大缓冲;非 DLY/REV 类型用通用路径,ctx[3] 落在 1KB 槽区。

**结论（工程不可用：G1on 实机失败）**:要在 B1on/G1on 上跑大状态自定义模块,静态证据指向
唯一可行方向——以 DLY/REV 身份(real_type=8/9,SONAME `ZDL_DLY_*`/
`ZDL_REV_*`)打包,让固件把外部 640KB 缓冲交给模块(B 组探针
B1dly704K 即为此验证);或把状态压进 1KB。

## 补充工具

- analysis/b1on_os/c00dec6c.dis / c00dd72c.dis / c00de040.dis /
  c00de400.dis:本轮用 TI dis6x 补拆的小块反汇编
- scripts/disdb.py:反汇编数据库 + 调用图 + 函数提取
- scripts/dumprange.py:按虚拟地址转储固件块
- docs/firmware_image_records.json:完整镜像记录清单

## 补充:FS 分区与效果清单(2026-08-16 第三轮)

### 12. Updater 内嵌 FS 分区格式

OS 镜像记录之后是 FS 分区(文件系统),B1on/G1on Updater 内各含同一 FS
的 2~3 份拷贝(引导/主区冗余):

- 文件目录:32B/条,`名字[12] + 0xFFFFFFFF×3 + 文件ID(u32) + 文件大小(u32)`;
  按类别分成多段目录(B1on 首段在 exe 0xC2B00,36 条)。
- 文件数据:ZDL 前有 4B 记录头(如 `99 00 FA 0F`)+ 4B 零,然后才是标准
  ZDL 包装(`NULL + SIZE + INFO + ELF`)。
- ZDL 包装精确布局(修正):ELF 起始 = 20 + header_size(标准 56 → ELF 在
  76);SIZE 块 = magic+payload(8)+header_size+elf_size,共 16B。

### 13. B1on v1.30 vs G1on v1.21 效果清单(实测差异)

| 项 | B1on 1.30 | G1on 1.21 |
|---|---|---|
| ZDL 包装总数(含冗余拷贝) | 138 | 151 |
| 去重后效果数 | 105 | 107 |
| 共享效果 | 43 | 43 |
| 独有效果 | 62(贝斯箱头/贝斯驱动/贝斯前级/贝斯调制等) | 64(吉他驱动/吉他箱头/NoiseGate 等) |

B1on 独有示例:SVT、B_MAN、FlipTop、BassDrive、DI5、Ba_Chorus、
Ba_Octave、PEDALWAH/B_PDLMNP 等(贝斯向)。
G1on 独有示例:Booster、OverDrive、T_Scream、Governor、DistPlus、
DistOne、Squeak、FuzzSmile、GreatMuff、MetalWRLD、HotBox、Z_Clean 等
(吉他驱动向)。

完整清单见 docs/FX_INVENTORY_B1ON_G1ON.txt;可复现脚本:
scripts/scan_updater_zdis.py(全量目录)与 scripts/compare_fs.py(差异)。

含义:两台设备 OS 相同,FS 不同——因此"同一 ZDL 在 B1on/G1on 上能否
加载"取决于它的 real_type/fxid 是否与目标设备 FS 中已有类别兼容
(社区经验:驱动类需设备已有同类效果才显示,与此 FS 结构吻合)。

### 14. FLST_SEQ.ZDT(设备内效果菜单序列)

启动注册表的数据源之一:FS 里的 FLST_SEQ.ZDT 定义**每类效果的显示
顺序**。结构:

```
头部: b">>>" + 24B零 + b"<<<" + 10B零 + b">>>" + 类别ID+9B零
每类: 12B文件名记录("NAME.ZDL" NUL补齐)...
类别结束: b"<<<" + 类别ID + 填充,再接 b">>>" + 下一类别ID...
```

类别 ID = INFO 的 real_type(0x01 DYN、0x02 FLT、0x03 DRV、0x04 AMP、
0x05 BASSAMP、0x06 MOD、0x07 SFX、0x08 DLY、0x09 REV、0x14/20 BASSDRV、
0x16/22 BASSPRE)。

实测菜单规模:

| 设备 | 菜单效果数 | 类别 |
|---|---|---|
| B1on 1.30 | 96 | DYN/FLT/BASSAMP/MOD/SFX/DLY/REV/BASSDRV/BASSPRE |
| G1on 1.21 | 105 | DYN/FLT/DRV/AMP/MOD/SFX/DLY/REV/PDL 等 |

完整顺序见 docs/B1ON_MENU_SEQUENCE.txt 与 docs/G1ON_MENU_SEQUENCE.txt;
解析脚本 scripts/parse_flst.py。

## 建议下一步 / Suggested next steps

1. 刷 B 组探针(B1dly704K),若 wobble 则 real_type=DLY 触发大区,按 DLY
   身份打包有状态模块即可(最省事)。
2. 继续静态:追 0xc00884e0 登记簇内 word7 的写入指令,锁定 real_type→
   激活函数映射表(无需硬件)。
3. 直接硬件验证 AmpNeve(按 docs/HARDWARE_TEST.md 序列)。
4. 把 48B/220B 注册表记录做成可导出的"FS 注册表转储器",长期可对照。
