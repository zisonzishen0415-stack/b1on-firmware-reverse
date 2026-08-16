# Zoom B1on / G1on 固件逆向总报告

日期:2026-08-16  ·  对象:B1on v1.30 与 G1on v1.21 官方固件

本报告汇总全部逆向成果,详细证据见各分卷文档(文末索引)。目标:逆向
B1on 固件,实现"自行编写 ZDL 模块并加载到 B1on/G1on 效果器"。

## 1. 设备与固件身份

- B1on v1.30 与 G1on v1.21 的 **OS 镜像逐字节相同**(11 个记录 SHA1 全同);
  差异只在 FS 分区(ZDL 列表/菜单)。
- SoC 为 TI C674x(C6000 内核),DSP 代码运行在 0xC007xxxx 区,L2 SRAM
  在 0x11800000/0x11F0xxxx,外部 DDR 在 0xC0xxxxxx。
- 固件镜像记录格式:`01 59 53 58`("YSX") + 小端地址(4) + 长度(4) + 数据;
  未列出的地址段是未初始化 RAM。

## 2. ZDL 效果模块格式

```
NULL(4) + "SIZE"(4) + payload=8(4) + header_size(4) + elf_size(4)
       + "INFO"(4) + info_size=48(4) + INFO(48B) + [BCAB/CABI] + ELF
ELF 起始 = 20 + header_size(标准 56 → 76)
```

INFO 48B:32B 版本串 + [32]real_type + [33]unknown1 + [34]knob_type +
[35]unknown2 + [36..37]sort_index(u16=fxid) + [38]bass_flags +
[39]sort_fx_type + [40..43]fx_version。

ELF:TI C6000 EABI、ET_DYN、小端;自定义 13 节精简布局可加载(GAIN
实机证明);加载器按符号名解析 `Dll_<Name>`/`SonicStomp`/`Fx_<GID>_<Name>`,
RELA 重定位与 MS-70CDR 同构。

描述符(SonicStomp):48B/行;行0 OnOff、行1 self(含 w28 成本浮点 @+0x28)、
参数行、末行哨兵 flags=0x04。**描述符内无状态区大小字段**。

## 3. 运行时 ABI

| ctx 槽 | 含义 |
|---|---|
| ctx[0] | Dll count |
| ctx[1] | 参数表 float[] |
| ctx[2] | 小状态区(滤波等) |
| ctx[3] | {base,end,span} 状态区描述符 |
| ctx[4]/[5]/[6] | 干/湿/输出累加缓冲 |
| ctx[11]/[12] | magic shuttle(必须原样搬运) |

音频按块处理:每回调 8 样本/声道(`LLLLLLLL RRRRRRRR`);输出是**累加**
而非覆盖。Dll 3 字段即可注册;G1on AMP 类需 CABI 块,SONAME 前缀必须
匹配 gid(`ZDL_FLT_`/`ZDL_DLY_`/`ZDL_AMP_`...)。

## 4. 启动注册表与槽激活

固件启动时按 FLST_SEQ.ZDT 顺序 + 各 ZDL 的 INFO 构建注册表
(0xC003F200 区):28B 元数据(real_type)、基址表、220B 效果记录、
fxid 表、48B 每槽记录(word7=激活函数、word8=音频处理器、word10=w28)。

槽激活链:`c0098b98`(入口)→ `c0098784`(分发)→ 48B word7 间接调用
(B.S2X)。每槽处理器表 0xC00DD528[slot] 由 48B word8 安装(c00beac0),
默认 0xc00c6840/44;音频引擎经 c00bada8 通用分发器调用。

预算检查(0xc00989e4):`Σw28 + 类别成本表(0xc00db120/138)` ≤ 210.0f;
w28 在整个 OS 中只在预算检查被读取——**它是纯成本,不决定状态区大小**。

## 5. 状态区机制(核心)

- 自定义效果(FLT/DYN/DRV...)拿到**每槽固定 1KB** L2 区
  (0x11800000+slot*0x400,启动清零),写超即死机。
- 延迟/混响类效果使用**外部 5×640KB 缓冲**
  (0xC01A5800+slot*0xAC440,启动清零,描述表在 0xc00df948)——即原厂
  DELAY "大区" 的来源。
- 分配路径由 per-effect 激活函数(48B word7)按 real_type 派发;w28 与
  描述符均不参与。
- **工程结论**:大状态自定义模块按 DLY/REV 身份(real_type=8/9)打包,
  待实机探针确认;或把状态压进 1KB。

## 6. FS 分区与效果清单

- Updater 内嵌 FS:4096B 块,11 系统块 + 数据块(6B 头 prev/next/size);
  文件表 32B/条(addr+size+12B名)。
- 全量目录:B1on 138 个 ZDL 包装(去重 105),G1on 151(去重 107);
  共享 43。完整清单见 docs/FX_INVENTORY_B1ON_G1ON.txt。
- 菜单 FLST_SEQ.ZDT:每类 `>>>`+ID(13B)+ 13B 文件名记录 + `<<<`+ID(13B);
  类别 ID = INFO real_type。B1on 96 项,G1on 105 项。

## 7. 工具链与加载路径

构建(全部本机验证):

```powershell
python -B build.py --smoke    # 直通测试模块
python -B build.py            # G1on AMP(CABI)
python -B build.py --b1on     # B1on BassAmp(BCAB)
AMPNEVE_GID=8 AMPNEVE_AUDIO_FUNC=Fx_DLY_AmpNeve python build.py  # DLY 变体
```

每次构建自动做 .obj 安全审计(禁 .fardata/.bss/SBR/switch 表)。

加载路径:

1. Zoom Effect Manager 文件夹加载(ZDL 层,无状态模块实机可用)。
2. 固件注入(scripts/zfe_inject.py):ZDL 写入 FS,回读哈希一致。
3. 注入 + 菜单(scripts/inject_effect.py):同时登记到 FLST_SEQ,
   效果出现在设备浏览器。B1on/G1on 成品固件均已在 dist/。

## 8. 验证状态与剩余项

| 项 | 状态 |
|---|---|
| 固件镜像/格式/注册表/ABI/FS/菜单解析 | 完成(静态,全部留脚本) |
| ZDL 工具链与模块构建 | 完成(构建+审计通过) |
| 无状态模块实机加载(GAIN) | 上一轮已实机确认 |
| 固件注入 + 菜单(文件层) | 完成(哈希/重解析一致) |
| DLY 身份大区假设 | 静态证据充分,**待实机探针确认** |

唯一剩余:刷 `probes/b1on_probe/out/B1sweepDLY.ZDL`,听 18 秒,报开头
连续 wobble 段数(≥11 = DLY 拿 640KB 大区)。

## 9. 文件索引

- docs/DEEP_RE_B1ON_G1ON.md:深度逆向报告(地址级证据)
- docs/ZDL_FORMAT.md:ZDL 容器/ELF/描述符格式
- docs/FIRMWARE_INJECTION.md:固件注入与菜单登记
- docs/HARDWARE_TEST.md:探针实验与硬件测试序列
- docs/FX_INVENTORY_B1ON_G1ON.txt:B1on/G1on 效果清单差异
- docs/B1ON_MENU_SEQUENCE.txt / G1ON_MENU_SEQUENCE.txt:设备菜单顺序
- scripts/:disdb、dumprange、check_probes、parse_flst、edit_flst、
  zfe_inject、inject_effect、scan_updater_zdis、compare_fs 等
- probes/b1on_probe/:13 个二分探针 + 2 个单文件扫描探针
- ampneve/:ZDL 构建工程(dist/ 含 G1on/B1on/DLY 变体)
- dist/:成品固件(注入 + 菜单版)
