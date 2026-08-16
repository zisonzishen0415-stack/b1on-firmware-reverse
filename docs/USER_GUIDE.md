# 用户操作手册(实机验证)

全部静态逆向已完成。剩下的只有一步实机确认,按本手册做即可收口。

## 你需要的东西

- 一台 Zoom B1on(或 B1Xon)效果器 + USB 线
- Zoom Effect Manager(ZEM,https://zoomeffectmanager.com)

## 第一步:探针(约 5 分钟,决定大状态模块能不能用)

1. 打开 ZEM,连接效果器,先**备份当前效果列表**。
2. ZEM 设置里"从文件夹读取效果",指向
   `probes/b1on_probe/out/`。
3. 把 **B1sweepDLY.ZDL** 写入设备(只装这一个)。
4. 在设备上选一个音色链,把该效果加进链里,把唯一旋钮 Arm 打到 1。
5. 从头播放/弹奏,**听 18 秒**,数"开头连续左右 wobble 的段数 N"
   (每段 1.5 秒):

| N | 结论 |
|---|---|
| 2(约 3 秒) | 仍是 1KB 槽区,DLY 身份无效 → 走小状态路线 |
| 11~12(约 17-18 秒) | DLY 身份拿到 640KB 大区 → 大状态模块可用 |
| 其他 | 按 N 查 probes/b1on_probe/README.md 解码表 |

6. 把 N 告诉我(或直接写进 README 的验证记录)。

## 第二步(可选,若 N≥11):刷大状态模块固件

1. 备份设备用户数据(固件更新会清空)。
2. 刷 [B1on_v1.30_+AmpNeveDLY_Menu_Updater.exe](dist/B1on_v1.30_+AmpNeveDLY_Menu_Updater.exe)
   (或 G1on 用 G1on_v1.21_+AmpNeveDLY_Menu_Updater.exe)。
3. 设备重启后,AMPNEVE 应出现在 **DLY(延迟)类别**;
   加载后弹奏,确认出声、旋钮可调、不卡死。

## 安全性

- 探针与固件都会覆盖设备数据:先备份。
- 一次只装一个探针;若设备卡引导,用 ZEM 刷回原厂效果或原厂固件。
- 注入固件的 OS 区与官方逐字节一致(已校验),风险仅来自新效果本身。

## 记录模板

```
设备型号: B1on / B1Xon / G1on / G1Xon
固件版本: 1.30 / 1.21
探针: B1sweepDLY / B1sweepFLT
wobble 段数 N:
卡死/异常:
AmpNeve_DLY 结果(出声/旋钮/卡死):
```
