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
| `linker_b1on_ext_2026-10-13.py` | 打完补丁的 `linker.py` 全文(权威副本,直接覆盖即可) |

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

配置:gid=8(DLY)、fxid=422、manifest_hw4(4 旋钮 Gain/Master/Level/Treble)。
构建环境:`AMPNEVE_TI_ROOT=D:\ti\ti-cgt-c6000_8.3.15\ti-cgt-c6000_8.3.15`,
`AMPNEVE_ZDL_ROOT=...\zoomreverse\ZoomMultistompZDL`,env:
`AMPNEVE_MANIFEST=manifest_hw4.json AMPNEVE_GID=8
AMPNEVE_AUDIO_FUNC=Fx_DLY_AmpNeve AMPNEVE_FXID=422
AMPNEVE_USE_OBJECT_INIT=1` + `AMPNEVE_DLL_FIELDS={3|5}` +
`AMPNEVE_AUDIO_VA={0x7800|未设}`。

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
