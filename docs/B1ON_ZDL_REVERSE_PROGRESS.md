# B1on ZDL 逆向进度（2026-08-15）

## 已完全确认

### ZDL 容器
- `NULL + SIZE + INFO + [BCAB/CABI] + ELF`；INFO 48B 全部字段解析。
- 加载器不校验版本字符串；SIZE 块结构必须正确。

### ELF / 加载器
- C6000 EABI, ET_DYN；原厂 36 节 vs 自定义 13 节，都能加载。
- B1on 1.30 加载器（c0080bf0 链）与 MS-70CDR（c00a6b68 链）逐指令同构。
- 动态表解析、RELA 重定位、符号解析（Dll_<Name>/SonicStomp）一致。

### 描述符 / Dll
- SonicStomp 48B/行；name 行 +0x28 = w28（DSP 成本）。
- w28 预算：B1on 上限 210.0f（c00989e4），MS-70CDR 226.0f；超限即失败/卡引导。
- Dll 额外字段（DELAY [4]=0x40 [5]=0x154；HALL [4]=0x26c）= tapmute/time_edit 偏移，与状态区无关。

### 运行时 ABI
- ctx[1]=参数表、ctx[2]=小状态、ctx[3]={base,end,span}、ctx[5]=fx、ctx[6]=输出累加、ctx[11]/[12]=magic。
- 原厂 DELAY/HALL/ROOM/PLATE/AIR/RVRSDLY/HPS/PTCHSHFT/SEQFLTR/B_ATWAH 使用 ctx[3]（反汇编全量确认）。
- B1on 每槽固定 1KB 状态区：0x1180f000 + slot*0x400（c00939c4/c007d760 清零）。
- 自定义效果写 ≥1KB 即死机 = 该 1KB 区域越界；OTT 80B 能跑与之吻合。

### B1on 效果注册表（新发现）
- 固件在启动时从 FS（FLST_SEQ.ZDT + ZDL INFO）构建注册表：
  - 0xc003f200 + effect*28：每效果 28B 元数据（含 real_type 等）
  - 0xc003f290/0xc003f2a8/0xc003f2c0/0xc003f2d8/0xc003f2e0：索引表
  - 0xc003fae8 + effect*13：13B 文件名记录
  - 0xc00407e8 + effect*220：220B/效果记录
  - 0xc0042ae8 + effect*16、0xc0042f48 + effect*4
  - 0xc003f204 + slot*28 → 基址 + effect*48：48B/效果记录（含 word3 上限值）
- MS-70CDR 固件不引用 0xc003f2xx（FS 布局不同）。
- 槽激活代码 c0098b98 用注册表记录做类型/上限检查并写每槽记录（0x11814e20+44*slot）。

## 剩余未知（唯一）

B1on 槽激活时用什么字段决定 ctx[3] 是 1KB 还是原厂 DELAY 的 ~700KB。
静态上已锁定到：注册表 48B/效果记录、每槽记录、w28、real_type。

## 决定性实验（已构建，待刷机）

`work/b1on_probe/out/` 13 个只读探针：
- A 组 7 个：阈值 640B..704KB（FLT, w28=20.0）→ 量出自定义状态区大小
- B 组 2 个：real_type=DLY（1K/704K）→ 测类型是否触发大区
- C 组 4 个：w28=15.55（1K/4K/64K/704K）→ 测 w28 是否触发大区

判读：哪个 704K 探针 wobble，就说明哪个字段（类型/w28）决定大区。

## 备选路径

- 从 B1on 通过 ZEM 导出完整 FS（含 0xc003f2xx 注册表），直接读每效果的 48B/220B 记录字段，对照自定义 vs 原厂。
