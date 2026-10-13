# 自制 ZDL 兼容检查单(B1on/G1on 目标 + 通用平台规则)

> 用途:每次把自制效果推向实机前的上线自检。来源两处:
> 1. `third_party/ZoomMultistompZDL/build/ABI.md` 与 `docs/STATE-ABI-PROGRESS.md`
>    —— MS-70CDR 平台**硬件验证过**的规则(我们的构建链同源);
> 2. 本项目对 B1on/G1on 的静态逆向成果(2026-10-13,见
>    `G1ON_FULL_RE_2026-10-13.md`)。
> 两平台 OS 不同,**共有规则与平台差异分开列**。

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
| **`.audio` 段 = 音频回调代码段,原厂一律链到 VA 0x7800**(描述符 48B 行 word8=a=音频函数 VA);自制链目前音频在 `.text@0`、`.audio` 空 | 第五轮结构差异项,是否致命待 loader 静态核实+实机(见 `G1ON_AUDIO_SEG_AND_STATE_ARCH_2026-10-13.md` §1) |

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

## 5. 待实机裁决

`B1sweepFLT.ZDL`(对照组,预期 N=2)/ `B1sweepDLY.ZDL`(关键组,N≥11
即大区成立)→ 之后把 ampneve 按 DLY 身份重打:

```powershell
$env:AMPNEVE_TI_ROOT = "D:\ti\ti-cgt-c6000_8.3.15\ti-cgt-c6000_8.3.15"
$env:AMPNEVE_GID = "8"
$env:AMPNEVE_AUDIO_FUNC = "Fx_DLY_AmpNeve"
python build.py   # 在 ampneve/zdl 下;cl6x 已于 2026-10-13 恢复
```

**2026-10-13 第五轮待办(实机前)**:静态核实 G1on loader 对音频
`.audio`@0x7800 段的处理(决定是否给自制 ZDL 扩 linker 输出二段式
ELF)——见 `G1ON_AUDIO_SEG_AND_STATE_ARCH_2026-10-13.md` §1/§4。

**DLY 变体已重建就绪(2026-10-13 晚)**:四形态矩阵 ×{真 DSP,烟测}全留档
(见 `patches/README.md` 哈希表);首选上机候选 = `ampneve/dist/AmpNeve.ZDL`
(**原厂分段 `.audio@0x7800` + 5 字段 Dll**)。刷机顺序:
1. **B1sweepFLT/DLY 探针**(8 月原件,判读 ctx[3] 尺寸);
2. `dist_smoke/AmpNeve.ZDL`(烟测,UI/加载);
3. `dist/AmpNeve.ZDL`(真 DSP);
4. 若 3 失败 → 依次试 `AmpNeve_stock3` / `AmpNeve_merged5` /
   `AmpNeve_merged`,每次一个变量。
5. **注册校验(2026-10-13 新增)**：自制 ZDL 经 ZEM 写入后,回读
   `FLST_SEQ.ZDT` 确认名字出现在对应类别段(见第五轮文档 §9;
   分类不可见怪癖的先查项)。
