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
