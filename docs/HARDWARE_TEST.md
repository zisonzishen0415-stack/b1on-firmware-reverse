# 硬件测试手册(B1on / G1on)

> 实验性质,任何一刷都可能让设备卡引导/死机。刷前先备份当前效果列表
(Zoom Effect Manager 的 Backup);出问题时用 ZEM 刷回原厂效果或原厂
固件,设备本身一般可恢复(冷启动)。

## A. ctx[3] 状态区大小实验(B1on,13 个探针)

目标:一次测出 B1on 给自定义 ZDL 分配的 ctx[3] 状态区大小,并找出
"哪个字段会让 B1on 分配大状态区"(w28 还是 real_type)。

原理:探针 DSP 只**读** `ctx[3][0..2]`,从不写状态区;当
`end-base >= 阈值` 时用声道 wobble(左右音量交替 0.08/1.80)报告成功,
否则直通。报告计数器写在已证明安全的 ctx[2]+0x18。

用法:音色链里放一个探针,把唯一旋钮 Arm 开到 1,听输出:

- 明显左右交替 wobble = 该阈值被满足(ctx[3] 至少这么大)
- 无声/直通 = 阈值未满足(或 Arm=0)

### A 组:状态区大小二分(FLT 类型,w28=20.0)

| 文件 | 阈值 | 含义 |
|---|---|---|
| B1sz0640.ZDL | 640 B | 下限 |
| B1sz001K.ZDL | 1024 B | 对照"写 1KB 即死机" |
| B1sz002K.ZDL | 2048 B | |
| B1sz004K.ZDL | 4096 B | |
| B1sz064K.ZDL | 64 KB | |
| B1sz512K.ZDL | 512 KB | |
| B1sz704K.ZDL | 704 KB | 原厂 DELAY 量级 |

### B 组:real_type=8 (DLY)(SONAME 前缀 ZDL_DLY_,w28=20.0)

| 文件 | 阈值 | 含义 |
|---|---|---|
| B1dly001K.ZDL | 1024 B | DLY 类型下是否还是 1KB |
| B1dly704K.ZDL | 704 KB | DLY 类型是否拿到大区 |

### C 组:w28=15.55(原厂 DELAY 精确成本,FLT 类型)

> 2026-08-16 静态更新:已确认 w28 只在预算检查(0xc00989e4)被读取,
> 不参与状态区分配;本组理论上可不刷,保留仅作复证(见 DEEP_RE_B1ON_G1ON.md)。

| 文件 | 阈值 | 含义 |
|---|---|---|
| B1w15501K.ZDL | 1024 B | 是否还是 1KB |
| B1w15504K.ZDL | 4096 B | |
| B1w15564K.ZDL | 64 KB | |
| B1w1557MK.ZDL | 704 KB | 是否拿到 704KB |

### 判读表

| 现象 | 结论 |
|---|---|
| A 组只有 0640/001K wobble,其余直通 | 自定义效果状态区 = 1KB,与崩溃阈值吻合 |
| B1dly704K wobble | real_type=DLY 触发大区 -> 按 DLY 身份打包即可 |
| B1w1557MK wobble | w28 触发大区 -> 改 w28 即可(按静态证据,预计不会发生) |
| 所有组都 wobble | B1on 其实给了大区,崩溃另有原因(再查) |
| 探针加载即死机/无音 | 问题不在状态区写入本身,而在文件其它特征 |

注意:一次只刷一个探针;某探针卡引导则用 ZEM 刷回原厂再继续。

## B. AmpNeve 硬件测试序列(G1on,照做顺序)

1. **Smoke**:`python build.py --smoke`,刷 `ampneve/dist_smoke/AmpNeve.ZDL`。
   验证效果出现在 AMP 分类、三个页面渲染、旋钮不冻结。若冻结 = 加载器/
   编辑处理器问题,与 DSP 无关。
2. **真实 DSP**:`python build.py`,刷 `ampneve/dist/AmpNeve_ZDL` 后弹奏。
   出现爆音/zipper/死机 = 每效果 CPU 预算超限(最大嫌疑:1024-tap 箱体 FIR)。
3. **压力**:把 AmpNeve 与延迟+混响放同一音色链,Gain 拉满弹奏。能扛住
   则记录固件版本与 fxid 行为(0x01A4 是否与同固件效果冲突)。
4. **回退**:若 2/3 失败,把 `tools/gen_coeffs.py` 的 IR 长度减半
   (AMP_CAB_IR_N),重新生成 `core/ampsim_coeffs.h` 再构建,CPU 降约 50%。
5. 只有设备能干净加载并出声后,才可宣称"硬件验证通过"。

## C. 固件注入刷机(进阶)

`dist/` 下有注入好模块的完整固件 Updater:

- `B1on_v1.30_AmpNeve_Updater.exe`(基于官方 B1on v1.30 Updater)
- `G1on_v1.21_AmpNeve_Updater.exe`(基于官方 G1on v1.21 Updater)

流程与 Zoom 官方固件更新一致(设备开机、USB 连接、运行 Updater)。
固件更新会覆盖设备内所有用户数据,先备份。
