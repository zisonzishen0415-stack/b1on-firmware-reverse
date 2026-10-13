# patches/ — 构建链本地补丁(B1on/G1on 用)

2026-10-13 起,本仓库对构建链(NGC 之外的第三方工具链 ZoomMultistompZDL)的
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
| `self_row_w28` / `cost_w28` | **已实现**:覆盖描述符自行的 w28 浮点(默认 20.0 不变) |
| `dll_fields` | 接受 3(**与现有全部产物一致**);5 = G1on AMP 专用 → 大声 `NotImplementedError`(未移植;原厂形状已从 DELUXE_R.ZDL 反汇编取得,见第五轮文档) |
| `amp_cabi_fxid` / `amp_cabi_default` | `None` = 通过;非 None → 大声 `NotImplementedError`(G1on AMP CABI 描述符路径未移植) |

**设计原则**:凡未移植的功能一律**大声报错**,绝不静默产出错误成品
(用户规则:数据与工作不能丢;错的成品比没有更坏)。

## 验证记录(2026-10-13)

1. 上游 third_party 克隆建 B1sweepFLT.ZDL → 与 8 月 fork 产物**逐字节 0 差异**;
2. shim 打进 user-fork 后重链 B1sweepFLT → 与 8 月产物差 **1 字节**:
   imageInfo 头字 h6 = 28(LineSel 1-2 参数形态)vs 32(Aug 构建);
   归属:user-fork 的**后期精化**(其注释含 G1on 单页 9 旋钮冻结的认知),
   对 >3 参数构建不影响头字(两家同为 21,23),且 fork 的 count=3 正是
   G1on 要求——**构建基准选定 user-fork**;
3. ampneve DLY 变体重建成功(见下)。

## 现有重建产物(硬件就绪,未刷机)

| 产物 | SHA256 | 备注 |
|---|---|---|
| `ampneve/dist/AmpNeve.ZDL` | `3C1D765CEFE0C67DA16A59A9E9C6AD3EFDEA858641185C45E6D970D0DD707542` | gid=8(DLY)、fxid=422、manifest_hw4(4 旋钮)、真 DSP |
| `ampneve/dist_smoke/AmpNeve.ZDL` | `E51304061AE6F4BCA758063A7EEC3C4B72287E5DF45578BBF3A0EEE34D244779` | 同配置,音频 NOP(先刷它) |

构建环境:`AMPNEVE_TI_ROOT=D:\ti\ti-cgt-c6000_8.3.15\ti-cgt-c6000_8.3.15`,
`AMPNEVE_ZDL_ROOT=...\zoomreverse\ZoomMultistompZDL`,env:
`AMPNEVE_MANIFEST=manifest_hw4.json AMPNEVE_GID=8
AMPNEVE_AUDIO_FUNC=Fx_DLY_AmpNeve AMPNEVE_FXID=422
AMPNEVE_DLL_FIELDS=3 AMPNEVE_USE_OBJECT_INIT=1`。

**已知与实机的最后差距**(第五轮发现,尚未修):产物 `.audio` 仍并入
`.text@0`(原厂全部样本 = `.audio` 独立段 @ VA 0x7800)。修它需要动
linker 的段布局,列为下一打包修正项。

## 注意

- 本补丁只覆盖 `build/linker.py`;fork 自带其余文件(blobs、stock_zdls)
  按原样使用;
- `probes/b1on_probe/out/` 的 15 个探针保持 **8 月原件不动**(已上判读表),
  不要用新链重建覆盖。
