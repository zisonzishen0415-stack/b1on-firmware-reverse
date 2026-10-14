# 自制 ZDL 兼容检查单(B1on/G1on 目标 + 通用平台规则)

> 用途:每次把自制效果推向实机前的上线自检。来源两处:
> 1. `third_party/ZoomMultistompZDL/build/ABI.md` 与 `docs/STATE-ABI-PROGRESS.md`
>    —— MS-70CDR 平台**硬件验证过**的规则(我们的构建链同源);
> 2. 本项目对 B1on/G1on 的静态逆向成果(2026-10-13,见
>    `G1ON_FULL_RE_2026-10-13.md`)。
> 两平台 OS 不同,**共有规则与平台差异分开列**。

## 0. 为什么固件全解析完了还需要实机?(常见疑问)

固件文件 = 程序本身。静态分析能读**文件里的每一行代码**——已完成
(1,642/1,642)。但"自制 ZDL 拿到的 ctx[3] 是 1KB 还是 640KB"这个
目标的答案**不在任何固件文件里**:

- 决定它的输入 = RAM 表(`0xD540/D558`、`0xD4F8/D510` 等,见第五轮
  文档 §2)——这些表位于镜像**空洞**(未加载区),固件里只有**读表的
  代码**,没有**写表的代码**(三路独立搜索已证)。初值由启动期/
  引导阶段写入,不落盘。
- 已证绑定层**无 real_type/字段门控**——即固件文本里根本不存在
  "DLY 给大区、FLT 给小槽"这样的判定语句。规则(如果有)发生在
  镜像外的运行时数据流里。
- 所以这不是"还没破解出来",而是**答案不在被解的对象里**:
  如同拿到完整菜谱也读不到"今天锅里放了几克盐"——那要去看锅。
  探针 = 让 DSP 自己把那个数字"念"出来的一次读取仪式。
- 同理,"加载后 UI/音频是否正常"是 56 字节头 + ELF 契约在真固件里的
  接受结果;静态已证明产物满足契约中所有**已写明**条款(结构全对齐),
  但部分条款(如分类可见性怪癖)本身以设备行为定义,实机是唯一裁判。

**2026-10-14 新基准(重要)**:社区项目更新线(`themanro/ZoomMultistompZDL`,
2026-09/10)已并入参考:①其 830 件原厂语料**独立证实**"`.audio` 可选、两种
布局均真机可用"(§5.1,硬件确认 StereoChorus/OTT/TapeEcho4/SyncProbe);
②其 `LOADER-SAFETY.md` 给出装载器 8 阶段结构 + 冻结成因目录(与我们清单
互补);③其 `G1on_*` 101 件与我们的 FS dump **零差集**(抽取互证);
④**Ziddle(C674x 模拟器,CC0)已授权并跑通(2026-10-14)**:WSL 内构建
matcheck rig(`work/setup_ziddle.sh`),首轮 A/B 发现**谱系级 init 约定差**
——他们 22 个发版效果 init 后参数已归一化(PASS),我们全部旧产物
init 后停在旋钮尺度默认值(FAIL,handler 才归一化);原厂 dis6x 复核证实
**B1on/G1on stock init 自身就逐个调 `*_edit` handler 物化**(§1 末行)。
已按 `materialize_init` 重建 **`AmpNeve_norm`(双 PASS,见 §5)**;
日志 `work/matcheck_2026-10-14{,_norm}.log`。
本地参考克隆:`refs/themanro-ZoomMultistompZDL`(只读)与
`zoomreverse/ZoomMultistompZDL-2026-10`(工作副本,已带 B1on 兼容 shim)。

## 1. 通用规则(MS 平台硬件验证,构建链内建部分检查)

| 规则 | 后果(若违反) |
|---|---|
| **SONAME 前缀必须 = 类别**:`ZDL_<类别>_<Name>.out`,与 gid/real_type 一致 | 固件回退"无分页 2 旋钮"渲染 —— **即"无 UI"症状** |
| 编译必须 `--mem_model:data=far`(静态变量走 MVKL/MVKH 绝对寻址) | 默认 SBR/B14 相对寻址读到垃圾 → 死机 |
| `.fardata` `memsz == filesz`,且保持小(>512B 冻结风险;"2KB 强制"是加载器校验) | 溢出到固件管理内存 → 冻结/卡引导 |
| Dll 入口体长度有讲究:8 指令极简版不稳定;NoiseGate 200B 逐字拷贝稳定;其中 MVK 立即数 = `2 + 参数数` | 切换效果时随机冻结 |
| `effectTypeImageInfo` 恰好 212 字节、3 个旋钮槽;`_infoEffectTypeKnob_A_2 = {20,15,11,0,2,0}` | 分页坏/冻结 |
| 无 `sinf/cosf/tanf/logf`(固件 RTS 里没有);`__c6xabi_divf` 可用(随构建链附带 rts blob) | 链接失败或运行崩 |
| 音频块 8 样本/声道 `LLLLLLLL RRRRRRRR`;float32;**Output 是累加**不是覆盖 | 声学损坏/吞掉下游尾音 |
| `ctx[3]` = `{base, end, span}` 大区描述符;`ctx[1]` 参数表,`params[0..4]` 为宿主保留 | 越界写/参数错位 |
| **`.audio` 段形态(0x7800 独立段 vs 合并 .text@0)** | **2026-10-14 全语料修正:两种皆为原厂合法形态**(285 件有 0x7800 段 / 540 件合并;G1on 在役的 160_COMP.ZDL 即合并形态)。**不是**加载器要求,矩阵两形态皆可上机 |
| Dll 字段数 | **实况(830 件扫描)**:5 字段(含 ctx[3]/ctx[4] 两条 STW)= 52 件,全部为 G1on_ 前缀**音箱族**;其余 734 件为 3 字段 → **5 字段 = G1on AMP 场景要求(gid4)**;非 AMP 构建 3 字段为原厂常态(矩阵两版皆合法) |
| **`_init` 必须物化参数**:逐个调用每个用户旋钮的 `*_edit` handler(2026-10-14:matcheck 契约 + 原厂 dis6x 双向证实——B1Xon_LIMITER init 4/4、G1on_DELUXE_R init 7/8) | 加载/换 patch 后参数不生效(实机=须动旋钮才活);旧"NOP init/等宿主扫 handler"约定已证与原厂不符。正确形态 = `materialize_init`(2026-10 谱系 linker,`ZDL_MATERIALIZE_INIT=1`) |

## 2. B1on/G1on 特有(本项目静态证据,101 个原厂 ZDL 实测)

**real_type ↔ SONAME 前缀表**(打包时照抄):

| real_type | 前缀 | real_type | 前缀 |
|---|---|---|---|
| 1 | `ZDL_DYN_` | 7 | `ZDL_SFX_` |
| 2 | `ZDL_FLT_` | 8 | `ZDL_DLY_` |
| 3 | `ZDL_DRV_` | 9 | `ZDL_REV_` |
| 4 | `ZDL_AMP_` / `ZDL_DCAMP_` | 15 | `ZDL_COMMON_` |
| 6 | `ZDL_MOD_` | | |

**实机级补充(250 个真模块目录 + 33 条真机 patch,2026-08-20 用户 B1on
1.30 实测,来源:`zoom-b1on-patches-manager/docs/protocol/VERIFIED_FACTS.md`
与 `%APPDATA%\ZoomB1onPatchesManager\catalog.json`)**:

| real_type | 类别 | patch group | 实测 dsp_cost(w28)范围 | real_type | 类别 | patch group |
|---|---|---|---|---|---|---|
| 1 | DYN | 0x0200 | 12.9–45.3 | 8 | DLY | 0x1000 |
| 2 | FLT | 0x0400 | 11.6–40.7 | 9 | REV | 0x1200 |
| 3 | DRV | 0x0600 | 30.4–82.7 | 11 | PDL(踏板) | 0x1400 |
| 4 | AMP/DCAMP | 0x0800 | 74.8–95.3 | 20 | BASSDRV | 0x0280 |
| 5 | **BASSAMP(B1on 音箱)** | **0x0A20** | 60.9–67.8 | 22 | BASSPRE | 0x02C0 |
| 6 | MOD | 0x0C00 | 13.7–64.2 | 12/13 | 贝斯类(实测存在) | — |
| 7 | SFX | 0x0E00 | 13.9–55.9 | | | |

**设备协议事实(同源实测)**:patch 内 fxid = INFO fxid `<< 1`(bit0=on);
组别由 real_type 经上表得出(互为交叉验证);B1on v1.30 实机文件 = **172 个**
(146 ZDL + 25 raw + `FLST_SEQ.ZDT` 4108B 模块清单);33 条出厂 patch 已抓取
解码(0 未知模块);**实机 33 条 patch 中不存在自定义 fxid**(与 8 月失败后
清理一致)。

**大区结构**(已逐字节挖出):

- 5 个槽缓冲:`0xC01A5800 + k*0xAC440`(k=0..4),每槽 `0xAC440`
  = 0xA0000(640KB 可用) + 0xC440(保护带);描述表 `0xC00DF948`
  存 5×{基址, 0xAC440};运行期数组 **`0xC00DD540[k]`(基址)/
  `0xC00DD558[k]`(长度)**(第五轮修正:旧文两数组标注相反),
  访问器 `c00bd260/c00bd26c`。挂载链(第五轮):f_c0088184(yield 任务)
  → f_c0088108(bind,读 D540/D558)→ f_c00b0e04;**全程无 real_type
  判定**——大区绑定是描述符数据 + 缓冲池数据流。
- **平台差异(重点)**:MS-70CDR 给自定义效果的 ctx[3] 默认就是
  ~705,536B(硬件探针,与 0xAC440 同量级);而 **B1on/G1on 非 DLY/REV
  类自定义效果实测只拿到 1KB 槽区**(2026-08 实机,写超即死机)。
  "按 real_type 把槽指向大区"的判定分支尚未静态钉死——
  **实机探针 B1sweepFLT/DLY 是唯一裁决**(报告 §9)。

**注册链**(自制 ZDL 落位顺序):48B 记录 word8(+8)→ 每槽处理器表
`0xC00DD528[slot]`(默认 0xC00C6840);word7(+0x1C)= 激活函数;
注册表 28B/效果 @ `0xC003F200`、220B/效果 @ `0xC00407E8`。

## 3. 失败症状 → 成因对照(用户实机历次现象)

| 症状 | 最可能成因 | 对应规则 |
|---|---|---|
| 效果出现但**无 UI** | SONAME 前缀与类别不匹配 → 回退 2 旋钮渲染 | §1 |
| **加载即冻 / 卡引导** | `.fardata` 过大 / `memsz≠filesz` / 缺 `data=far` / 用了 SBR 寻址 | §1 |
| **调旋钮冻结** | 借用的 edit handler 缺 `state[7]` 尾调用(UI postbox 不同步)——MS 侧 SyncPrV2 实测 | §1/STATE-ABI |
| **切换死机** | 写超 ctx[3] 实际大小(非 DLY 类 = 1KB) | §2 探针 |
| 直通 / bypass | 音频函数未进块循环 / 注册失败 | 探针日志 |

## 4. 上线前自检(本仓库现成)

```powershell
# 元数据类(rt/fxid/SONAME 前缀/ELF entry)
python scripts/check_probes.py probes\b1on_probe\out

# 构建内建审计(禁 .fardata/.bss/SBR/switch 表;每次 build.py 自动跑)
# ampneve/zdl/build.py → tools/check_zdl_obj.py
```

2026-10-13 复核:15 个探针(含 B1sweepFLT/DLY)全部 **OK**。

```bash
# 归一化契约(init 物化 + handler 归一化)离线验证 —— Ziddle matcheck(WSL)
/root/ziddle/ziddle-source-1787802520/target/release/matcheck --params 4 --bypass 1 <zdl>
# 合格 = after init PASS + after handlers PASS
# 2026-10-14 实况:AmpNeve_norm 双 PASS;旧矩阵 11 件 after-init FAIL(已知缺陷)
```

## 5. 待实机裁决

`B1sweepFLT.ZDL`(对照组,预期 N=2)/ `B1sweepDLY.ZDL`(关键组,N≥11
即大区成立)→ 之后把 ampneve 按 DLY 身份重打:

```powershell
$env:AMPNEVE_TI_ROOT = "D:\ti\ti-cgt-c6000_8.3.15\ti-cgt-c6000_8.3.15"
$env:AMPNEVE_GID = "8"
$env:AMPNEVE_AUDIO_FUNC = "Fx_DLY_AmpNeve"
python build.py   # 在 ampneve/zdl 下;cl6x 已于 2026-10-13 恢复
```

**2026-10-14 首选候选更新(重要)**:Ziddle matcheck 修正后,首选上机
候选 = **`ampneve/dist/AmpNeve_norm.ZDL`**(merged + 3 字段 Dll +
2026-10 谱系 + **materialize init**;SHA256 `B024D12E…`,烟测
`19EC3CF5…`;构建确定性已验证)——init 后参数即归一化,与原厂 stock
行为一致(matcheck after-init + after-handlers 双 PASS)。**旧的"原厂
分段+5 字段"矩阵(stock5 等)降为回退组**:其 init 属旧约定(参数不
物化),实机预期"加载后须动旋钮参数才生效"。`AmpNeve_norm5`(分段+
5 字段+物化)待 dll5 移植进 2026-10 树后生成。`.audio@0x7800` 形态
问题已由全语料修正(两种皆原厂合法),不再是阻塞项。

刷机顺序(2026-10-14 版):
1. **B1sweepFLT/DLY 探针**(8 月原件,判读 ctx[3] 尺寸);保险版
   `B1sweepFLT_seg.ZDL` / `B1sweepDLY_seg.ZDL` 同目录——探针保持
   8 月原件不动(判读表冻结;其 readout 不依赖 init 约定)。
2. **`dist_smoke/AmpNeve_norm.ZDL`**(烟测,UI/加载);
3. **`dist/AmpNeve_norm.ZDL`**(真 DSP);
4. 若 2/3 失败 → 回退组逐个换变量:`AmpNeve_stock5`(旧主候选,
   分段+5 字段)→ `stock3` → `merged5` → `merged`;注意回退组带着
   已知 after-init 缺陷,判读时把"参数不生效"归到此因。
5. **注册校验**:自制 ZDL 经 ZEM 写入后,回读 `FLST_SEQ.ZDT` 确认名字
   出现在对应类别段(见第五轮文档 §9;分类不可见怪癖的先查项)。
