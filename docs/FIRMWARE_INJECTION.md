> **项目状态（2026-08-16 修订）：失败。**
> 经 G1on 实机多次验证，自制 ZDL **无法在 G1on 上稳定工作**（表现为：无 UI、bypass、或切换死机）。
> 此前文档中的“已验证 / 可用 / 可运行 / 已对齐 / 可收口”等表述，均不代表 G1on 实机可用。
> 本项目的 ZDL 目标当前**未达成**，现状为失败；任何后续结论不得以“G1on 可用”为前提。

# 固件级 ZDL 注入(不需要 ZEM)

除"Zoom Effect Manager 读文件夹"外,还有第二条把自定义 ZDL 装进
B1on/G1on 的路径:直接改写官方 Updater 内嵌的文件系统(FS),刷入后
固件在启动时把注入的 ZDL 当作原厂文件加载。

## 原理

Updater 内嵌 FS 采用 4096B 块:

- 11 个系统块:启动头 + 4 份文件表(每表 2 块,表头 `55 AA 00 01 04 00` 区)。
- 数据块:每块 6B 头(prev u16 / next u16 / size u16)+ 数据。
- 文件表条目:32B = 起始块 addr(u16) + 0x01 + size(u32) + 名字(12B,NUL 补齐)。
- 空闲块链表决定可注入位置;注入时把文件按 4090B/块切开写入,更新表与链表。

ZDL 数据本身带 4B 记录头 + 4B 零 + 标准 `NULL+SIZE+INFO+ELF` 包装,
直接整体写入即可,无需转码。

## 用法(已验证 2026-08-16)

```powershell
$py = "C:\Users\29517\AppData\Local\Programs\Python\Python311\python.exe"
$s  = "C:\Users\29517\Documents\ChatGPT\b1on-firmware-reverse\scripts\zfe_inject.py"

# 1) 查看原厂 Updater 的文件表
& $py -B $s list "firmware\B1on_v1.30_official\...\Zoom B1on System v1.30 Updater.exe"

# 2) 注入自定义 ZDL(可多个)
& $py -B $s inject <原厂Updater> ampneve\dist\AmpNeve_DLY.ZDL -o dist\B1on_v1.30_+AmpNeveDLY_Updater.exe

# 3) 按 Zoom 官方流程刷入该 Updater(设备开机、USB 连接、运行 exe)
```

注:文件名取 ZDL 文件名前 8 字符(去尾下划线)+ `.ZDL`,如
`AmpNeve_DLY.ZDL` → `AMPNEVE.ZDL`;设备内效果名由 ZDL 描述符决定,与
文件名无关。

## 验证结果(2026-08-16)

- 官方 B1on 1.30:789 块,610 已用,168 空闲;文件表 124 个文件。
- 注入 `AmpNeve_DLY.ZDL`(28950B)后:表项 `AMPNEVE.ZDL @ block 159`,
  回读内容 SHA-256 与源文件**一致**,原 124 文件全部完好。
- 上一轮产物 `dist/B1on_v1.30_AmpNeve_Updater.exe` 同样可列:
  `MODREV.ZDL @159`、`_SVT.ZDL @286`(SVT 被替换为自定义版)。

## 与 ZEM 路径的关系

| 路径 | 原理 | 适用 |
|---|---|---|
| ZEM 文件夹加载 | 设备端 ZDL 加载器读 FS | 已硬件验证(无状态模块) |
| 固件注入 | 改写 FS,启动时加载 | 无需 ZEM;刷一次整机生效 |

两条路径都依赖同一 FS/ZDL 格式;固件注入适合交付成品固件,ZEM 适合开发迭代。

可复现脚本:scripts/zfe_inject.py(端口 ZoomFirmwareEditor v0.98 逻辑)。

## 进阶:注入效果并加入设备菜单(2026-08-16 已验证)

只注入 ZDL 后,效果在 FS 里但未必出现在设备浏览器。设备菜单由
FLST_SEQ.ZDT 定义(结构见 DEEP_RE_B1ON_G1ON.md 第 14 节:每类
`>>>`+ID(13B) + 13B 文件名记录 ×N + `<<<`+ID(13B))。一体工具
scripts/inject_effect.py 同时完成两件事:

```powershell
& $py -B scripts\inject_effect.py <原厂Updater> <zdl> <real_type/cat_id> -o out.exe
```

`cat_id` = INFO real_type(1 DYN、2 FLT、3 DRV、4 AMP、5 BASSAMP、6 MOD、
7 SFX、8 DLY、9 REV)。已验证:

```
[inject] AMPNEVE.ZDL: 28950 bytes -> block 159
[menu] added AMPNEVE.ZDL to category 08 (FLST_SEQ 4108 -> 4121 bytes)
```

验证结果:注入文件表项正确、ZDL 内容 SHA-256 与源一致、FLST_SEQ 重解析
后 AMPNEVE.ZDL 出现在 DLY 类别(延迟效果之后)、9 个类别结构完好、
其余 124 文件不受影响。

配套脚本:

- scripts/edit_flst.py:FLST_SEQ 解析/插入(list / add)
- scripts/inject_effect.py:ZDL 注入 + 菜单登记一体
