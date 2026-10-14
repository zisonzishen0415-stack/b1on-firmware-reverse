# patches/ — 构建链本地补丁(B1on/G1on 用)

2026-10-13 起,本仓库对构建链(第三方工具链 ZoomMultistompZDL)的
本地修改集中在这里,保证可重建、不静默丢失。

## 背景(为什么需要补丁)

- 2026-08 使用的扩展版 linker 位于 `probes/b1on_probe/repeat98_tmp`
  (repeat98 工作树私有状态),**该目录已随清理删除,且公开仓库均无此版本**;
- ampneve/探针构建脚本依赖它独有的 LinkerConfig 参数:
  `bass_flags` / `dll_fields` / `amp_cabi_fxid` / `amp_cabi_default` /
  `self_row_w28` / `cost_w28`;
- 重建路径:以**用户自己的 G1on 感知 fork**
  (`github.com/zisonzishen0415-stack/ZoomMultistompZDL`,本地克隆在
  `D:\zisonzishen\development\g1oncontrol\zoomreverse\ZoomMultistompZDL`)
  为基础,补一层 shim。

## 文件

| 文件 | 说明 |
|---|---|
| `linker_b1on_ext.patch` | 对 fork 仓库(commit 2dda9600)`build/linker.py` 的 git diff(仅 shim) |
| `linker_b1on_ext_2026-10-13.py` | 打完补丁的 `linker.py` 全文(权威副本,直接覆盖即可)——**注意:2026-10-14 发现该文件与实际工作树已漂移,以 diff 为准** |
| `linker_2026-10_ext_2026-10-14.patch` | **2026-10 工作树**(`zoomreverse/ZoomMultistompZDL-2026-10`)相对上游快照(`refs/themanro-ZoomMultistompZDL`)的**完整差异**(147 行):B1on 兼容 shim + **dll_fields=5 移植**(2026-10-14)+ materialize 之上的本地改动。重建 = 对上游 2026-10 的 `build/linker.py` 应用本 diff(按目标路径调整 -p 层级后 `git apply`) |

## shim 语义(逐条)

| 参数 | 处理 |
|---|---|
| `bass_flags` | 接受;`!=0` 大声 `NotImplementedError`(B1on BCAB 路径未移植) |
| `self_row_w28` / `cost_w28` | **已实现**:覆盖描述符自行的 w28 浮点(默认 20.0) |
| `dll_fields` | **已实现**:3 = NoiseGate 200B 段(全部既有产物同款);**5 = 原厂 G1on AMP 形状**(从原厂 DELUXE_R.ZDL 反汇编逐字抄录的 64B 段,ctx[3]/ctx[4] 指向 NOP_RETURN stub VA)。G1on AMP(gid=4)必须 5;其余类别两种均可试 |
| `amp_cabi_fxid` / `amp_cabi_default` | `None` = 通过;非 None → 大声 `NotImplementedError`(G1on AMP CABI 描述符路径未移植;CABI 包装块由 ampneve `add_cabi()` 后处理完成) |
| `audio_va` | **已实现(0x7800)**:音频函数独立可执行段(原厂形态);0 = 旧合并形态。附加:该模式下 text 对象码从 0x20 起,**任何函数不会落在 VA 0**(描述符 h/a 的 0 可能被 loader 视为"缺省") |

**设计原则**:凡未移植的功能一律**大声报错**,绝不静默产出错误成品。

## 验证记录(2026-10-13)

1. 上游 third_party 克隆重链 B1sweepFLT.ZDL → 与 8 月 fork 产物**逐字节 0 差异**;
2. shim 打进 user-fork 后重链 → 与 8 月产物差 1 字节(imageInfo 头字 h6:
   28 vs 32,fork 后期 LineSel 精化;>3 参数构建不受影响,且 fork 的
   count=3 为正 G1on 要求)→ **构建基准 = user-fork + shim**;
3. **原厂分段形态静态验证通过**(对照原厂 ZDL):
   - `B1sweepFLT`(audio_va=0x7800):PHDR = text@0 / **audio@0x7800 (r-x)** /
     const@0x80000000 / fardata / dynamic(与原厂 DELAY.ZDL 同构);
     `.audio` 节 a=0x7800 f=0x6 al=32;描述符 row1 a=0x7800;
   - **ampneve**(audio_va=0x7800):同上;row1 h=0x20(init)、a=0x7800、
     w28=20.0;`.audio` 2016B。

## 现有重建产物(硬件就绪,未刷机)

**四形态矩阵 × {真 DSP, 烟测}**,全部留档(linker 确定性已验证:
同配置重建逐字节复现):

| 文件(dist/ 与 dist_smoke/ 同名两份) | 形态 | 真 DSP SHA256 | 烟测 SHA256 |
|---|---|---|---|
| **`AmpNeve.ZDL`(首选上机候选)** | **原厂分段 + 5 字段 Dll** | `AE9AEED15F9C9A6882977F746EE07933AA2F49009A13B8BF29C979C84762AFF3` | `44597621BC9E93EDAC00D2E1E6CEB261C7D3810C022C94ECE765E8813FC8EC69` |
| `AmpNeve_stock3.ZDL` | 原厂分段 + 3 字段 Dll | `76ED18ED46C7761AEE9B14E677AD6BCABE2E67A4F61D0D12F68749CCD0D34459` | `9B87BB7EE07F8AEE7922C1C936542293ED3DD58B06BDCFCA7652752DF404FA81` |
| `AmpNeve_merged5.ZDL` | 旧合并 + 5 字段 Dll | `14155A8B3A13F2C8736B399A8D73B24B518775E66A313D1620A7A17A82028663` | `75F5F298E64640380B0E5038959A4D249E9738672D10C3DB5946F6A034EDB4CD` |
| `AmpNeve_merged.ZDL` | 旧合并 + 3 字段 Dll(8 月世系形态) | `3C1D765CEFE0C67DA16A59A9E9C6AD3EFDEA858641185C45E6D970D0DD707542` | `E51304061AE6F4BCA758063A7EEC3C4B72287E5DF45578BBF3A0EEE34D244779` |
| `AmpNeve_them10.ZDL` | 合并 + 3 字段(2026-10 树,无物化) | `3592BF6815642DF2E7E85CDA1ED620D000900ECD753777282FACE2CCC3DED397` | `449A9196D79EF24E4B61AE621AAD66B1CC87677E02FFBBBDFD765D8B02E71B41` |
| **`AmpNeve_norm.ZDL`(2026-10-14 新首选)** | 合并 + 3 字段 + **materialize init**(2026-10 树) | `B024D12E19DAC7F6640BCCA0ACCE70C2F262764BA3A23DB8E5C6D18CB601A999` | `19EC3CF5C2835B595E7F87BC4C2E3DEFB50677EE6ADBC5785DB4F56FE8FAB596` |
| `AmpNeve_norm5.ZDL`(备选:AMP 形状) | 合并 + **5 字段 Dll** + materialize init | `A769597DAF7B547E9CBB74BD057EAE55E5135C3AE482AA5B0E706CCAAF72A7CE` | `258B296595D5CB0067BB842CC62393527E2EAB61E10EBF3C7A8D6D633CDBF659` |

**2026-10-14 晚:上表 norm/norm5(r1)已被发现带跨段重定位 bug——
文件已改名 `*_r1_bug.*` 留档(勿刷)。修复版:**

| 文件 | 形态 | 真 DSP SHA256 | 烟测 SHA256 |
|---|---|---|---|
| **`AmpNeve_norm_r2.ZDL`(修复后首选上机候选)** | 合并 + 3 字段 + materialize + **reloc fix** | `68E351C1B301480922A43F3426898E6612228B76368D0BBD888BCBD93505DB78` | `8717A569E1F2A505226264F1B8B6AB4C6B801B0B3CF2A1305637DF0AC896D14B` |
| `AmpNeve_norm5_r2.ZDL` | 合并 + 5 字段 + materialize + reloc fix | `12C916C3D843881186228216D371F9DCBD33DA8B7638E1083C375B93056E0EF0` | `1943D382E9424D097CEB35CE804B513FA7DBD2D968DB4185529B6BF817D5E02D` |

(修复前矩阵 stock5/stock3/merged5/merged/them10 全部同病,留档不删,勿刷;
详见 `docs/RELOC_BUG_ROOT_CAUSE_2026-10-14.md`)

配置:gid=8(DLY)、fxid=422、manifest_hw4(4 旋钮 Gain/Master/Level/Treble)。
构建环境:`AMPNEVE_TI_ROOT=D:\ti\ti-cgt-c6000_8.3.15\ti-cgt-c6000_8.3.15`,
`AMPNEVE_ZDL_ROOT=...\zoomreverse\ZoomMultistompZDL`,env:
`AMPNEVE_MANIFEST=manifest_hw4.json AMPNEVE_GID=8
AMPNEVE_AUDIO_FUNC=Fx_DLY_AmpNeve AMPNEVE_FXID=422
AMPNEVE_USE_OBJECT_INIT=1` + `AMPNEVE_DLL_FIELDS={3|5}` +
`AMPNEVE_AUDIO_VA={0x7800|未设}`。

## 2026-10-14 增补 2:跨段 PCR 重定位 bug 修复(根因级)

- `_apply_relocs` 的"段起点补偿"(`rel['addend']=该指令文件偏移`)误用于
  **跨段** PCR 重定位:`.audio` 内对 `.text` 核心函数的每次调用都飞到
  "目标+调用点偏移"。两棵树同源代码,同日各自修复(只对同段补偿)。
- 完整证据链与验证:`docs/RELOC_BUG_ROOT_CAUSE_2026-10-14.md`。
- **探针不受影响**(对象无 .text/无跨段 PCR 重定位,已用 obj_syms.py 验证)
  ——8 月原件与 _seg 保险版**保持不动、可直刷**。
- 修复后工作树差异已重生成:本目录两个 patch 文件均已含修复。

## 2026-10-14 增补 1:Ziddle 离线验证 + 物化 init(重要)

- **首轮 A/B(Ziddle matcheck)**:themanro 自产 Gyre.ZDL after-init PASS;
  我们全部旧产物 after-init **FAIL**(init 后 params 停在旋钮尺度默认
  值/原始旋钮值,handler 才归一化)。根因 = init 未物化参数——
  详见 `docs/CUSTOM_ZDL_COMPAT_CHECKLIST.md` §1 末行/§5。
- **原厂 dis6x 复核**(`work/stock_init_materialize_evidence_2026-10-14.txt`):
  B1Xon_LIMITER init 直呼 4/4 个 `*_edit` handler、G1on_DELUXE_R init
  7/8 → **materialize=原厂约定**,修复方向即 2026-10 谱系 linker 的
  `materialize_init`(env `ZDL_MATERIALIZE_INIT=1`)。
- **norm 构建环境**:`AMPNEVE_ZDL_ROOT=...\zoomreverse\ZoomMultistompZDL-2026-10`,
  `ZDL_MATERIALIZE_INIT=1`,**不设** `AMPNEVE_USE_OBJECT_INIT`,
  `AMPNEVE_DLL_FIELDS=3`,不设 `AMPNEVE_AUDIO_VA`(`AmpNeve_norm5` 同环境,
  `AMPNEVE_DLL_FIELDS=5`)。构建行输出
  `init: materializing 4 param(s) at load (_init @ 0x2340, 384B)`;
  确定性已验证(重建逐字节复现)。构建日志 `work/norm_build_2026-10-14.log`。
- **能力图(2026-10-14 更新)**:fork 树 = dll5 ✓ / materialize ✗;
  **2026-10 树 = materialize ✓ + dll5 ✓**(当日移植;Dll 字节与 fork
  产物逐字核对,全同仅 2 个 role-VA 立即数差 = 各自 NOP_RET 地址);
  `audio_va` 在 2026-10 树仍为响亮 NotImplemented(全语料修正后已降级为
  可选轴向,未移植)。`norm5`(合并+5 字段+物化)**已生成**,matcheck 双 PASS。
- **澄清(无数据丢失)**:10-14 一次 dll5-in-2026-10 尝试失败时,有两个
  文件被误命名为 `AmpNeve_norm5.ZDL`——经哈希核对它们 = stock5 的
  逐字节副本(非新产物),已删除;stock5 原件与全部矩阵文件未动。

**5 字段 Dll 验证(反汇编)**:ctx[0]=行数、ctx[1]=描述符 VA、ctx[2]=imageInfo VA、
**ctx[3]=ctx[4]=NOP_RETURN stub VA(0x1B60,安全返回)** — 与 8 月 fork 的
约定一致,形状逐字对齐原厂 DELUXE_R。3 字段回归:与 8 月探针产物
仍差 1 字节(已知 imageInfo h6 精化差,无行为影响)。

## 注意

- 本补丁只覆盖 `build/linker.py`;fork 自带其余文件(blobs、stock_zdls)
  按原样使用;
- `probes/b1on_probe/out/` 的 15 个探针保持 **8 月原件不动**(已上判读表),
  不要用新链重建覆盖;
- 未刷机!所有产物上机前先看 `docs/CUSTOM_ZDL_COMPAT_CHECKLIST.md` §5
  的刷机顺序(先探针 B1sweepDLY → 再烟测 → 再真 DSP)。
