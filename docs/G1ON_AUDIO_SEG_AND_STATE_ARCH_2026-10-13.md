# 第五轮发现:`.audio` 段 = 音频回调代码段(原厂一律 @ VA 0x7800)+ 状态体系全图

日期:2026-10-13(同日第五轮)。工具:TI dis6x 语料(`analysis/b1on_os/*.dis`,
经 `scripts/disdb.py` 查询)+ `full_zdl_dump.py` + 恢复的 TI cl6x/dis6x 8.3.15。
证据文件:`analysis/zdl_desc_2026-10-13/`(6 份 ZDL 完整 dump + 门控函数 TI 汇编)。

## 1. 决定性结构差异:自制 ZDL 全部缺 `.audio`@0x7800 段

原厂样本(全为 G1on 原厂 ZDL,描述符以 `full_zdl_dump.py` 解出):

| 效果 | real_type | `.audio` VA | `.audio` 大小 | 描述符 row1(h=激活/init 处理器,a=音频入口) |
|---|---|---|---|---|
| DELAY.ZDL | 8 | 0x7800 | 1088 | h=0x584 `Fx_DLY_Delay_init` · **a=0x7800** · w28=15.55 |
| HALL.ZDL | 9 | 0x7800 | 1728 | — |
| AUTOWAH.ZDL | 2 | 0x7800 | 1536 | — |
| CRY.ZDL | 2 | 0x7800 | 800 | — |

自制(全部,含 B1sweepFLT/DLY):**`.audio` 段存在但 size=0、不可执行;音频函数
在 `.text@0`,描述符 row1 的 `a=0x0`**——与全部原厂样本结构不同。

- 构建链约定(`third_party/ZoomMultistompZDL/build/linker.py`):音频函数必须
  `#pragma CODE_SECTION(Fx_..., ".audio")`(否则 linker 直接报错);但 MS 版
  linker 把 audio 合并进 `.text` @ VA 0(`TEXT_VA=0`, `AUDIO_OFF=0x0000`)——
  自制文件即此形态。
- **描述符行 = 48B 记录**:`name[12]` + {max, def, pedal, ?, **word7=h(激活/init
  处理器 VA)**, **word8=a(音频入口 VA)**, ?, w28=cost, flags}。旧文档"48B
  记录 word8 → 每槽处理器表"与此吻合(DELAY 的 word8=0x7800=其音频函数 VA)。
  w28=15.55 恰为 DELAY 的成本值(只进预算检查,§旧结论不变)。
- **0x7800 与启动清零**:`f_c00bd350` 先 `memset(0x11800000, 0, 0x7800)`,而
  **0x7800 = 5 × 0x1800**;全部原厂 `.audio` ≤ 0x1800(最大样本 1728 < 6144)。
- **假设(强,尚未逐指令钉死)**:每槽音频代码竞技场 = `0x11800000 + slot*0x1800`
  (6KB/槽,可执行 RAM;原厂音频代码按槽复制、以 0x7800 为虚拟基址)。自制 ZDL
  无 0x7800 段是否致命 = 待实机 + loader 处理 0x7800 段的函数静态核实。

## 2. 状态体系全图(全部有反汇编出处;本轮新增)

### 2.1 每槽运行时表

位于 RAM 空洞 `0xC00DBA84..0xC00DD72C`(**镜像未加载区域**——这正是 §7.10
"三路搜索无写入者"的最终解释:表不在镜像里,由启动期代码/引导阶段填充;
"无写入者"结论修正为"写入者不在镜像数据中"):

| 地址 | 内容 | 初始化/使用 |
|---|---|---|
| `0xD4F8[5]` | 指向 840B(0x348) 小状态池的指针 | `f_c00bea38`:`memset(D4F8[i],0,0x348)` |
| `0xD510[5]` | 指向 672B(0x2A0) 小状态池的指针 | `f_c00bea38`:`memset(D510[i],0,0x2A0)` |
| `0xD528[5]` | 每槽处理器 | 默认 `0xC00C6840`(空)/哨兵 `0xC00C6844`;`f_c00beac0` 安装 `D528[slot]=*(obj+0x20)` |
| `0xD540[5]` | **大缓冲基址**(各 0xAC440) | 访问器 `f_c00bd26c`;`f_c00bd350`:`memset(D540[i],0,D558[i])` |
| `0xD558[5]` | **大缓冲长度** | 访问器 `f_c00bd260` |
| `0xD570[5]` | 绑定标志 | `f_c0088108` 置 1;`f_c0088184` 清零 |
| `0xC0043000 + slot*0xD4` | 每槽效果对象:3 头字 `{flags, D4F8[i], D510[i]}` + 50×`0xC00Cxxxx` 指针表 | 构建者 `f_c00abd20` |

**修正**:旧 §7.4 写"`0xC00DD558[k]`=基址、`0xC00DD540[k]`=长度"——两数组标注
相反,应为 **D540=基址、D558=长度**(据 `f_c00bd350` 的 `memset(base,0,len)`
实参序反汇编逐条读出)。

### 2.2 挂载链(全部走通)

```
f_c00c5740(启动初始化: …→ f_c00bea38(清 D4F8/D510 池+复位 D528)→ …
           → f_c00bd2a4(硬编码 5×memset 0xC01A5800+k*0xAC440)
           → f_c00bd350(memset(0x11800000,0,0x7800) + 经 D540/D558 清五缓冲))
f_c008b548(slot, arg) 链提交: …→ f_c0088184(slot, arg) → …
           (若 D528[slot]==0xC00C6844 → f_c00beac0 安装处理器)
f_c0088184 = 注册收尾任务:yield(续点 0xc00881e4,返回 10)→ 恢复后自 0xC0043000
           对象读描述符流,对字符串表 0xC00DA140("SIZE" 等)校验 → 成功路径
           f_c0088108(bind);尾调处理器 → 返回后扫 ".ZDL"
f_c0088108(slot,…) = 绑定:经访问器读 D540/D558 → f_c00b0e04(slot,{base,len})
           → 置 D570[slot]=1 → yield
f_c00a5fa0 = 每块调度:obj=*(0xC003F200+slot*28+4);尾调 *(obj+0x1C)
```

**全程无任何 real_type 判定**——"大/小区按 real_type 路由"在本层不成立;
实际是"描述符数据 + 大缓冲池绑定"的数据流。real_type 影响的是别处
(UI 渲染/SONAME 前缀回退/预算,**见检查单 §1**)。

## 3. 工具链状态(本轮更新)

- **cl6x/dis6x 已恢复**:TI CGT 8.3.15 安装于
  `D:\ti\ti-cgt-c6000_8.3.15\ti-cgt-c6000_8.3.15\`(bin/ 内含 cl6x、dis6x)。
  获取方式:**匿名直链** `dr-download.ti.com/software-development/
  ide-configuration-compiler-or-debugger/MD-vqU2jj6ibH/8.3.15/
  ti_cgt_c6000_8.3.15_windows-x64_installer.exe`(30,786,256B,SHA256
  `A7255AED0F5CFA944A79D3DCE23D793DCB6AE85387657FB25A27EFF61E31FBE6`;
  `--mode unattended --prefix <dir>` 静默安装)。→ **自制 ZDL 重建通道打通**。
- TI dis6x 语料 `analysis/b1on_os/*.dis` 在盘上,`scripts/disdb.py` 直接查询
  (本轮 callers/callees/find 全部靠它;callp 目标以 dis6x 为准)。
- **GNU tic6x objdump(WSL 自建)两条实测规则**:① 只接受 **32 字节对齐**的起
  始地址(否则整段 "Address … is out of bounds",非对齐段确实未被解码——
  修正 §7.10"链 B 全反汇编"为"3 个对齐段完成、4 个非对齐段未出");② **callp
  打印的目标地址不可信**(显示值未按重定位计算),以 TI dis6x/Ghidra 为准。

## 4. 对"自制 ZDL 能正确工作"的直接意义

打包修正候选(实机前按此优先):

1. **音频函数置于 `.audio`@0x7800 的二段式 ELF**(需扩 linker 输出;
   MS 单段@0 形态在 G1on 是否被接受 = 先做 loader 对 0x7800 段处理的静态核实,
   再上实机);
2. 描述符 row1 的 `h`/`a` 指向正确(init/音频入口);
3. 既有三条(检查单 §1:CABI/stub/init 物化参数);
4. 实机探针步骤不变(总报告 §9);`probes/b1on_probe/out/` 文件已就绪。

## 5. loader 定位进展与否定结果(同日)

- **chain A(0x1180F800 区,4 块)首次反汇编完成**:`work/chainA/chainA.dis`
  (14,753 行;4 块起始地址全部 32 字节对齐,GNU objdump 一次通过;
  包装脚本 `work/wrap_c118.py`)。自此三个镜像区(主 OS / 链 A / 链 B)
  全部有反汇编产出。
- **链 B 覆盖闭合**:4 个非对齐起始段已从对齐基址补解
  (`work/slice_chainB_mis.py` + `work/dis_mis.sh`,产物
  `work/chainB/mis_*.dis`),全部确认为**数据表**(重复字节模式/undefined
  指令),非代码。链 B 代码 100% 覆盖。
- **否定结果:ELF 魔数(0x7F454C46,含 hex/十进制拆分形式)在主 OS、
  链 A、链 B 全部已解码语料中均不存在**。推论:DSP 固件不做标准 ELF
  解析;ZDL 的 ELF 组装/转换很可能发生在 **PC 侧(ZEM/更新工具)或
  链 B 未解码的 4 个非对齐数据段之外的其他环节**,DSP 侧消费的是
  已打包的记录(包装串 "SIZE" 出现在 0xC00DA140 校验 ✓ = DSP 会读包装
  文本,但 ELF 解析未见)。**下一次会话待查**:0xC002D000 记录描述符的
  填充者(文件扫描器)/ "SIZE" 包装字节进入 RAM 记录的那一段拷贝路径。
  已知 0xC002D000 的用户 = `c00ab1xx-c00ab4xx` 家族(记录读写原语,
  `f_c00ab120/f_c00ab230/f_c00ab2f0/f_c00ab418/f_c00ab4f8`)。

**2026-10-13 本轮终**:探针硬件步骤(§9)不变;`.audio` 二段式与
loader 核实列为下一静态目标。

## 7. 记录表(0xC002D000)填充链 — 已打通(同日续)

前文的"下一次会话待查:0xC002D000 记录描述符的填充者"已闭环:

- **表结构**:24 字节/记录 @ `0xC002D000 + idx*24`;名字在 +0 起(逐字节
  串,查名比较前 10~12 字节);`+0x10` 与 `+0x14`(=上界/长度)两个字段;
  复位 `f_c00ab120`:`memset(0xC002D000, 0, 0x1B0)`(432B = 18×24)。
- **填充者 = `f_c00ab2f0` 真身**(c00ab3a0-c00ab3d2):按索引变量
  `*+B14[20]` 取 `idx*24` 基址,写 +0x10、+0x14,并循环
  `STB *A4++ ← LDB *A5++` 逐字节写入名字。
- **注册 API 家族**(c00ab1xx-4xx):
  - `f_c00ab18c(name)` = 按名查表(SPLOOP 逐字节比较);
  - `f_c00ab208` = 清零扫描状态桩;`f_c00ae3b4` = 注册后处理(字符串
    规范/长度);`f_c009b740` 为其上游依赖;
  - `f_c00ab214(name)` = 注册入口(查不到→复位扫描态→处理后);
  - `f_c00ab230(dst,src,len)` = **带界读**:长度受记录 +0x14 上界约束
    (f_c0088184 挂载任务与 c0088ce8/c008f7b8/f_c008fbb8/f_c00b75e0
    使用);
  - `f_c00ab2f0` 被 `f_c00ab418`(同类解析器)调用。
- **上游命令层**:`f_c0090500` = **49 项命令分派器**——命令字节在
  `0xC006D6C8`,`0xC00DD72C + cmd*4` 为函数指针表(即镜像块
  `cc00dd72c_900` 的内容),逐项调用 worker
  (f_c0090328/f_c009020c/f_c0090120/f_c0090068/f_c008ffb8/f_c0090000/
  …/f_c008f980);其调用者 = `f_c00843xx` 事件家族(USB/UI 事件处理)。
- **注册一条记录的全路径**:`f_c008980` 从镜像模板 `0xC006D6C9`
  (13B:12 字节名 + 1 字节)复制到 `0xC0070EC8`,`f_c00ab214(name)`
  注册 → 表条目最终由 `f_c00ab2f0` 落盘;挂载任务 f_c0088184 再以
  `f_c00ab230` 带界读回消费。

**意义**:ZDL/效果数据从"命令层→注册 API→记录表→挂载任务"的完整
数据通路已无盲区;填充者不在引导 ROM,而在主 OS 的命令处理家族
(f_c00843xx → f_c0090500 → 注册家族)。

**补充(同轮末,f_c0088184 中段 final walk)**:中段对描述符记录的处理
已定到寄存器级——**帧槽(B15[1]/[2]/[4]/[5]/[6])全函数只有读、没有写**:
记录字节由**被调函数直接写入调用者帧**(调用处 `A4 = B15+4` 作为缓冲
指针,见 0x81e8/0x8200 等)。绑定调用实参 = {A4=记录首字(*B15[1]),
B4=记录第 7 字(*B15[6]),A6=槽号};守卫按 {0,4}/{0,0x10} 分帧校验。

**寄存器级歧义已闭合(同轮终)**:按 C6000 延迟槽语义(调用后 5 取指包内
的指令在**被调函数入口前**执行),`f_c0088108` 中 0x8120/0x8156 的
`MV.L1 A11,A4`(A11=槽号)正是两次访问器调用的实参设置——
**两个访问器接收的都是槽号**:`D540[slot]`=本槽大缓冲基址、
`D558[slot]`=长度。自洽性三重印证:①5 项数组 ↔ 5 槽;②同函数随即
置 `D570[slot]=1`;③另一读法(记录首字=0 作索引)会使所有效果索引
同一缓冲、与五缓冲池矛盾。**结论:绑定路径把"本槽大缓冲 {base,len}"
交给框架,全程无 real_type/字段门控**;效果最终看到的 ctx[3] 由此
下游(f_c00b0e04 与音频分派)决定——探针仍是"效果实际拿到多少"的
量尺,但"绑定层有无类型门"的疑问正式关闭。

## 8. 实机证据并入(2026-10-13 晚,来源:用户其他项目树)

从 `D:\...\g1oncontrol\zoom-b1on-patches-manager`(2026-08-19/20,
对用户本人 B1on 1.30 实机做读写并逐次回读验证)与
`%APPDATA%\ZoomB1onPatchesManager\catalog.json`(250 个真模块目录)
并入以下**实机级事实**(全部已在检查单 §2 更新):

- **真机文件 172 个**:146 ZDL + 25 raw + `FLST_SEQ.ZDT`(4108B 模块清单);
  33 条出厂 patch 已抓取并 100% 解码;
- **patch 编码**:patch fxid = INFO fxid `<< 1`(bit0=on);real_type →
  patch group 全映射(1→0x0200 … 9→0x1200,11→0x1400 PDL,
  **5→0x0A20 BASSAMP**,20→0x0280 BASSDRV,22→0x02C0 BASSPRE);
- **250 模块 × {real_type, w28 成本} 分布**已统计(如 DLY 15.2–127.7、
  DCAMP 74.8–95.3、BASSAMP 60.9–67.8)——检查单新表;
- **实机 33 条 patch 里不存在自定义 fxid**(8 月失败后设备未见残留);
- 附:该项目的 `src/zdlparse/` 是与本项目独立的第二套 ZDL 解析器
  (可作交叉对照),`docs/protocol/VERIFIED_FACTS.md` 为实机协议存档;
  其 FLST 直读未完成(块游标不前进),模块清单最终以 ZEM 库交叉核对兜底。

## 9. FLST_SEQ.ZDT(模块注册表)格式破译(2026-10-13 晚)

`FLST_SEQ.ZDT`(G1on FS 副本 4108B;真机列目录同尺寸)= **已注册模块
注册表**,ZEM 安装效果时写入:

- 结构:**13 字节名字槽**(12 字符 + NUL)连续排列,按类别分组;
  组边界标记 `3c 3c 3c 00 <组序>` + `3e 3e 3e 00 <计数>`(16 字节);
- **G1on 类别构成(与类别顺序)**:DYN 6 → FLT 10 → DRV 18 →
  **AMP/DCAMP 22** → MOD 20 → SFX 4 → DLY 9 → REV 11 = **100 个注册模块**
  (与 FS 的 101 个 ZDL 文件相比,唯一未注册者 = `CMN_DRV.ZDL`——
  共享/公共模块,推测作为依赖被引用而不单独立项);
- 无每模块几何/尺寸字段(纯名字表)——ctx[3] 尺寸问题仍只归探针裁决;
- **实机日新增必检项**:用 ZEM 安装自制 ZDL 后,经已验证的读取路径
  回读 FLST,确认自定义名出现在对应类别段(如 DLY 段)——"装好后
  分类浏览器不可见"的社区怪癖(需先装一个同类原厂效果)与注册表
  机制一致,此检查可直接定位该类问题。

## 6. 构建链重建 + ampneve DLY 产物(2026-10-13 晚,同一轮续)

**问题**:8 月用的扩展版 linker(`repeat98_tmp`,私有)已删;公开仓库
(repeat98 上游 @4ec75ee 与用户 fork @2dda9600)均无其独有的
LinkerConfig 参数(bass_flags/dll_fields/amp_cabi_*/self_row_w28/cost_w28),
ampneve 构建脚本直接报错。

**重建方案与验证**(细节与证据:`patches/README.md`):

1. 上游克隆重链 B1sweepFLT.obj → 与 8 月 fork 产物**逐字节 0 差异**;
2. 以**用户 fork**(含 G1on 感知的 imageInfo 精化——"广告参数总数会让
   G1on 单页渲染 9 旋钮→无 UI/冻结")为基准,补 shim:
   `self_row_w28/cost_w28` 实作;`bass_flags!=0`/`dll_fields=5`/
   `amp_cabi_*!=None` **大声 NotImplementedError**(不静默产出错误成品);
3. user-fork 重链探针与 8 月产物差 1 字节(imageInfo h6: 28 vs 32,
   fork 后期 LineSel 精化;>3 参数构建不受影响,且 fork 的 count=3 为正
   G1on 要求)→ **构建基准 = user-fork + shim**;
4. **ampneve DLY 变体重建成功**:
   - `ampneve/dist_smoke/AmpNeve.ZDL`(音频 NOP,先刷)
     SHA256 `E5130406…4779`
   - `ampneve/dist/AmpNeve.ZDL`(真 DSP;gid=8、fxid=422、
     real_type=8、SONAME `ZDL_DLY_AmpNeve`、manifest_hw4 4 旋钮)
     SHA256 `3C1D765C…7542`,28,950B
   构建命令见 `patches/README.md`;
5. 未移植项(5 字段 Dll=gid4 AMP 用、amp_cabi、B1on BCAB)全部
   **拒绝构建**;5 字段的原厂真实形状已从 DELUXE_R.ZDL 反汇编取得
   (ctx[3]/ctx[4] 两条 STW + 角色 VA),移植入口明确。
6. **`.audio`@0x7800 打包修正已实现(同日续)**:shim 新增 `audio_va`
   参数(0=旧合并形态;0x7800=原厂分段形态:音频函数独立可执行
   PT_LOAD,text 从 0x20 起避免函数落 VA 0)。静态对照原厂 ZDL 验证:
   PHDR 五段结构与 DELAY.ZDL 同构、`.audio` 节 a=0x7800 f=0x6、
   描述符 row1 a=0x7800、h 非零。**ampneve 两形态各留档**:
   原厂分段 `dist/AmpNeve.ZDL`(76ED18ED…4459)+ 烟测版
   `dist_smoke/AmpNeve.ZDL`(9B87BB7E…FA81);旧合并形状保留为
   `*_merged.ZDL`(3C1D765C…7542 / E5130406…4779)。刷机顺序不变
   (先探针,再烟测,再真 DSP)。`probes/b1on_probe/out/` 15 个探针
   保持 8 月原件不动。
