> **项目状态（2026-08-16 修订）：失败。**
> 经 G1on 实机多次验证，自制 ZDL **无法在 G1on 上稳定工作**（表现为：无 UI、bypass、或切换死机）。
> 此前文档中的“已验证 / 可用 / 可运行 / 已对齐 / 可收口”等表述，均不代表 G1on 实机可用。
> 本项目的 ZDL 目标当前**未达成**，现状为失败；任何后续结论不得以“G1on 可用”为前提。

# ZDL AMP 类契约(固件取证记录)

> 来源:全部结论来自 Updater/固件镜像字符串表与 ZDL 二进制逐字节对比,
> 不包含推断。时间:2026-08-16。

## 1. B1on/G1on 同平台证据

从两个官方 Updater 提取固件镜像,对比:

| 区域 | B1on v1.30 | G1on v1.21 | 结果 |
|---|---|---|---|
| OS 主代码(0xC0078D20, 0x4F860B) | Updater 偏移 0x564DC | 同偏移 | **逐字节相同** |
| 数据区(0x1180xxxx, 0x92A0B) | 偏移 0x4AB20 | 同偏移 | **逐字节相同** |

结论:两机 OS 与数据区完全相同,差异仅在 FS 分区。

## 2. FS 决定可用类别(OS 无硬编码前缀白名单)

- 在两个 Updater 中搜索 `ZDL_*` 字符串:全部位于 FS 区域
  (B1on 0x0CB05D–0x3D21DE;G1on 0x160BE1–0x3D44F7),OS 代码区
  (0x56500 起)内没有 ZDL_ 字符串。
- 因此 SONAME 前缀不是 OS 硬编码白名单;加载器按 FS 里的文件列表
  与 ZDL 自身 SONAME 工作。

## 3. 各类别 SONAME 前缀(Updater 字符串表)

### B1on v1.30 FS

`ZDL_BASSAMP_*`(SVT/HRT/GK 等)、`ZDL_BASSDRV_*`、`ZDL_BASSPREAMP_*`、
`ZDL_DLY_*`、`ZDL_DYN_*`、`ZDL_FLT_*`、`ZDL_MOD_*`、`ZDL_PDL_*`、
`ZDL_REV_*`、`ZDL_SFX_*`。

### G1on v1.21 FS

`ZDL_AMP_*`(12 型号:BG_CRUNCH/BG_DRIVE/DZ_DRIVE/FD_VIBRO/HW_STACK/
MATCH_/MS_CRUNCH/MS_DRIVE/TANGERIN/TW_ROCK/US_BLUES/VX_COMBO)、
`ZDL_DCAMP_*`(9 型号)、`ZDL_COMMON_DRV`(公共驱动,54 处)、
`ZDL_DRV_*`、`ZDL_DLY_*`、`ZDL_DYN_*`、`ZDL_FLT_*`、`ZDL_MOD_*`、
`ZDL_PDL_*`、`ZDL_REV_*`、`ZDL_SFX_*`。

## 4. G1on 原厂 AMP 类 ZDL 契约

证据样本:`G1on_TW_ROCK.ZDL`(AMP)、`G1on_MS_1959.ZDL`(DCAMP)。

### 4.1 文件与依赖

- SONAME:`ZDL_AMP_<Name>.out`(DCAMP 为 `ZDL_DCAMP_<Name>.out`)。
- **额外依赖 `ZDL_COMMON_DRV.out`**,并有 PLT 符号
  (`Fx_CMB_Amp` / `Fx_CMB_DualClipperAmp`)——AMP 类音频通过 PLT
  调用公共功放内核。
- wrapper 携带 CABI 段(AMP/DCAMP 专属;22/22 个 G1on 功放型号都有)。

### 4.2 导出符号

`Dll_<Name>`、`Fx_<CAT>_<Name>`(+`_init`/`_onf`/`<param>_edit`)、
`effectTypeImageInfo`、`picEffectType_*`、`_Coe`、
`_infoEffectTypeKnob_*`、效果名对象(如 `TW_ROCK`/`MS_1959`)。

### 4.3 描述符(48B 条目表)

```
OnOff        func=onf
<Name>       max=0xFFFFFFFF, func=init, audio_ptr=音频函数地址(非 0)
<knob>×7     func=<param>_edit
CAB          max=0, def=0x04000000|fxid, func=0
OUT          max=4, func=outputSelect 处理器, flags=0x4(哨兵)
```

## 5. 我们的 AmpNeve 与 G1on 原厂 AMP 的差异清单

### 已对齐(本次修改)

- 描述符符号名:`SonicStomp` → `AmpNeve`(原厂为效果名对象)。
- CAB 条目 func:`NOP stub` → `0`(原厂为 0)。

### 仍存在的差异(未修改)

- 效果名条目 `audio_ptr=0`(原厂非 0;repeat98 注释称 audio@0 已在
  B1on 硬件验证可运行,此差异保留但未在本项目实机验证)。
- OUT 条目 func 为 NOP stub(原厂为 outputSelect 处理器;我们没有实现
  该处理器)。
- 无 `ZDL_COMMON_DRV` 依赖与 PLT(原厂 AMP 类全部携带)。
- 旋钮 9 个(原厂 AMP 7 个)。

## 6. 打包器修改记录

- `third_party/ZoomMultistompZDL/build/linker.py`:
  - 描述符符号名由硬编码 `'SonicStomp'` 改为 `cfg.effect_name`;
  - CAB 条目 func 由 `_alloc_nop_va()` 改为 `0`。

## 7. 实机结论与下一步（2026-08-16）

**实机结论：自制 ZDL 在 G1on 上无法稳定工作（无 UI / bypass），项目现状失败。**

1. 实机验证本次对齐后的 `AmpNeve.ZDL`(G1on AMP, CABI)。
2. 若仍死机,对齐 `ZDL_COMMON_DRV` 依赖/PLT(需实现或借用公共功放
   内核),这是当前最大的结构级差异。
3. 记录实机结果,更新本文件。
