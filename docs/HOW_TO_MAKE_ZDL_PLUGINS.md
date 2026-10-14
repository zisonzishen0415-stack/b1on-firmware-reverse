# 如何正确制作 ZDL 插件(G1on/B1on/MS 系列)——2026-10-14 实证版

> 本文是**全流程实证总结**:每一条规则都有离线模拟器(Ziddle)或原厂
> 反汇编/语料证据。文中两个完整案例:AmpNeve(9 参数音箱)与
> Reverson(9 参数反转混响),均已离线双 PASS + 真实音频渲染。
> 配套:`docs/CUSTOM_ZDL_COMPAT_CHECKLIST.md`(上线自检)、
> `docs/RELOC_BUG_ROOT_CAUSE_2026-10-14.md`(两个根因级 bug 档案)。

## 1. ZDL 是什么(解剖)

```
+---------------------------+
| 00 00 00 00  "SIZE" ...    |  wrapper: NULL + SIZE(payload/hdr/elf 尺寸)
| "INFO" + 48B 描述:         |  real_type(1..15) / knob_type / fxid(u16)
|   fxid_version "1.00" ...  |  / bass_flags / sort_fx_type(=real_type)
| [可选 "CABI"/"BCAB" 块]    |  分类: AMP(gid4)=CABI,BASSAMP(gid5)=BCAB
| \x7fELF (TI C6000 EABI)    |  ---- 以下为 ELF ----
|   .audio  = 音频回调代码段  |  VA 0x0(合并形态)或 0x7800(分段形态,皆原厂合法)
|   .text   = 编译器其余函数  |  跨段调用由 .rela.dyn 在加载时重定位
|   .const  = 系数表/IR 表    |  绝对寻址(far 模型)
|   .fardata= 小数据          |
|   .dynamic/.rela.dyn        |
|   描述符 48B×(2+参数数)     |  word7=init VA, word8=audio VA(部分形态)
|   Dll 入口 200B/64B         |  写 ctx[0..4]: {行数, 描述符VA, imageInfoVA,
+---------------------------+     [role3, role4](5 字段版)}
```

## 2. 运行时 ABI(ctx 槽位,已在 Ziddle harness + 原厂语料交叉验证)

| 槽 | 内容 | 备注 |
|---|---|---|
| ctx[0] | 0 | |
| ctx[1] | **params 表指针** | params[0]=开关(1.0=on); params[5..13]=用户旋钮(0..1 归一化); 原厂 raw rail 0..0.14,**读参数一律用 zoom_param_norm() 归一化** |
| ctx[2] | state 头指针 | 部分原厂效果用(Reverb/Chorus 系) |
| ctx[3] | **大区描述符 {base,end,span}** | 自定义效应唯一可靠的持久状态区;B1on 上尺寸未知(探针裁决中),MS-70CDR≈705KB;描述符本身必须校验(魔数+版本) |
| ctx[4] | DRY 缓冲 | 只读 |
| ctx[5] | **WET/fxBuf** | **就地读写**——效果把输出写回这里(本世系约定) |
| ctx[6] | ACC 累加缓冲 | 另一种输出约定(累加);本世系不用 |
| ctx[7] | 编辑收尾回调(handler 尾跳) | init/handler 期间必须可用 |
| ctx[11]/[12] | **magic shuttle** | 音频回调**第一件事**必须 `*(ctx[11])[0]=ctx[12][0..]` 原样跳传,否则魔法丢失 |
| ctx[21]/[31] | 旋钮读值/曲线回调 | handler 用 |
| ctx[39]/[40]/[45]/[46]/[51] | 除/幂/log 等数学回调 | |

音频块 = **8 样本/声道,`LLLLLLLL RRRRRRRR`**;float32。

## 3. 构建链(本仓库的可用组合)

- **编译器**:TI CGT 8.3.15(`D:\ti\ti-cgt-c6000_8.3.15\ti-cgt-c6000_8.3.15`);
  flags: `--c99 --opt_level=2 -mv6740 --abi=eabi --mem_model:data=far`
  (**必须 far**——SBR 相对寻址读垃圾)。
- **链接器/打包器**:`zoomreverse/ZoomMultistompZDL-2026-10/build/linker.py`
  (**含全部修复**;完整差异 = `patches/linker_2026-10_ext_2026-10-14.patch`)。
- **构建脚本模板**:`ampneve/zdl/build.py`(带 manifest、审计、CABI 注入)、
  `zoomreverse/.../src/custom/reverson/build.py`(env: `REVERSON_ZDL_ROOT`)。
- **关键开关**:`ZDL_MATERIALIZE_INIT=1`(物化 init,§4.1)、`dll_fields=3|5`、
  `audio_va=0|0x7800`、`synth_edit_start_index`、`use_object_edit_handlers`。

## 4. 七个必须遵守的规则(每条都有翻车史)

### 4.1 `_init` 必须物化参数(materialize_init)
换 patch/重载后,音频函数应立刻读到**当前旋钮值的归一化**。做法 =
`_init` 逐个调用每个用户旋钮的 `*_edit` handler(2026-10 linker 的
`materialize_init` 生成"guard ctx[31]→B+ADDKPC 逐个 handler"的修正体)。
**证据**:原厂 B1Xon_LIMITER init 直呼 4/4、G1on_DELUXE_R 7/8;
matcheck after-init 检验(§6)。旧"等宿主扫"约定 = 实机"动旋钮才活"。

### 4.2 PCR 分支位移 = target − **(pc & ~31)**
C674x 以**取指包基准**(而非指令地址)加位移。若用指令地址编码,
每个非 32 对齐调用点都偏 `(addr & 31)` 字节——表现为"调用落到前一个
函数的返回桩 → 静默无处理 / 随机执行 / NaN"。**这是 2026-08 全部实机
失败的最终根因**(见根因档案)。

### 4.3 跨段 PCR 重定位**不加**"段起点补偿"
`_apply_relocs` 的 addend(仅对同段)已修:`.audio→.text` 直接解析到
符号 VA。错用会让每次调用多飞一个调用点偏移。

### 4.4 状态住在 ctx[3] 大区,带魔数守卫
- 首块:读描述符 → 校验(base/end/span 非零、4 对齐、尺寸够)→
  魔数不符则**清零+初始化+写魔数+当块直接返回**;下一块起才处理。
- 魔数头建议 16B:{magic, version, 两个 denormal 抖动种子}。
- 40 行代码模板见 `ampneve/zdl/ampsim_zdl.c` 与 `reverson_zdl.c`。

### 4.5 denormal 必须冲刷
ZDL 构建要启用核心的"ZDL 模式"宏(如 `AMPNEVE_ZDL_STATIC`),它同时
(a) 把 API 折成 static 供 cl6x 内联、(b) 开启 FLUSH_DENORM。
漏定义的教训:输出 NaN(2026-10-14 实测)。

### 4.6 旋钮 handler 配置
- 前 2 个旋钮:stock LineSel blob(`build/linesel_handlers.bin`);
- 第 3 起:synthesize LineSel 克隆(`synth_edit_start_index=2`,两处
  立即数被打补丁:knob id 与 params 偏移);
- **AIR knob3 blob 不要用**(2026-10-14:在 Ziddle 里撞未实现指令+打转);
- 全部 handler 会被 materialize init 逐个调用,必须都能安全返回。

### 4.7 分类与包装
SONAME 前缀 = 类别(`ZDL_DLY_`/`ZDL_REV_`/`ZDL_AMP_`...);gid 与
real_type 一致(REV=9,DLY=8,AMP=4...);G1on AMP(gid4)加 **CABI** 块
(后处理 `add_cabi()`,22/22 原厂 G1on amp 均带);B1on BassAmp(gid5)
用 **BCAB**;5 字段 64B Dll 仅 G1on AMP 场景需要,其余 3 字段 200B 为
原厂常态。gid8 等非 AMP 构建 3 字段即可。

## 5. 状态尺寸预算

`Reverson_state_size(44100)` ≈ 160KB(FDN 关)→ 需大区 ≥ 512KB
(glue 里的 floor 守卫);AmpNeve 状态 34KB。**B1on 给自定义效果的
ctx[3] 究竟多大 = B1sweep 探针的唯一使命**(判读表见 checklist §5)。

## 6. 离线验证流程(每次构建必跑,~3 分钟)

```bash
# 1) 契约:init 物化 + handler 归一化(双 PASS 才算合格)
matcheck --params 9 --bypass 1 <file>.ZDL
# 2) 音频:干信号 → WET 抓取(立体声),看 NaN/幅度/DSP 负载
zdlrun <file>.ZDL in.f32 out.f32 --out-wet --knobs <9个> --budget 400000000
#    - NaN=0;peak/rms 与 x86 离线渲染器(gcc 编译 core)同量级;
#    - 每块 cycles 中位数 = 真实 DSP 负载(如 AmpNeve ~86k、Reverson ~14k)
# 3) 确定性:同配置重建逐字节复现
```
工具在 `work/ziddle_rig/zdlrun.rs`(+`deploy_zdlrun.sh`)、
`work/{make_audition_input,f32_to_wav,analyze_audio_out}.py`。

## 7. 上机流程

按 `docs/CUSTOM_ZDL_COMPAT_CHECKLIST.md` §5:探针(B1sweepFLT/DLY,
判读大区尺寸)→ 烟测(audio_nop)→ 真 DSP → 回读 FLST 确认注册 →
(分类不显示时先装一个该类原厂效果,ZEM 怪癖)。

## 8. 两个完整案例(2026-10-14,全部离线验证通过)

| | AmpNeve(整个,9 参数) | Reverson(9 参数) |
|---|---|---|
| 来源 | `ampneve/core/ampsim.c` + `zdl/ampsim_zdl.c` | `zoomreverse/core/*.c` + `src/custom/reverson/reverson_zdl.c` |
| 类别 | gid 4(AMP)+CABI 块 | gid 9(REV) |
| 状态 | 34KB(ctx[3],memL/memR 两个实例) | ~160KB 环缓(FDN 关闭) |
| 构建 | `AMPNEVE_MANIFEST=manifest.json`(9 参数) + ZDL_MATERIALIZE_INIT=1 | `REVERSON_ZDL_ROOT=<2026-10树>` + ZDL_MATERIALIZE_INIT=1 |
| matcheck | 双 PASS | 双 PASS |
| 音频 | peak 0.96/rms 0.20(吉他全曲,86k cyc/块) | peak 0.09(NaN=0,14k cyc/块) |
| 最终哈希 | `744F786E…857B` | `AF077DC5…EF9A` |
| 试听 | `work/desc/AmpNeve_full_audition.wav` | `work/desc/Reverson_audition.wav`(渲染产出后) |

**修复前后对照(同一产物)**:修复前音频回调 1 块 >2 亿周期或崩跳野地址;
修复后 4.5k~86k 周期、NaN=0、与 x86 参照同型。
