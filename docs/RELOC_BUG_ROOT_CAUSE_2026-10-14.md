# 根因档案:音频回调跨段分支重定位 bug(2026-10-14)

**一句话**:构建链(用户 fork 与 themanro 2026-10 树**同源**)给 `.audio` 段的
跨段 PCR 分支重定位错误地加上了"调用点文件偏移"补偿,导致**每个音频函数
对 `.text` 内核心函数的调用都飞到"目标+调用点偏移"的随机地址**——
实机上表现为回调执行乱码/看门狗冻结;Ziddle 里表现为跳出野地址崩溃或
天文数字周期。**这是 2026-08 实机失败的代码级根因(全部历史产物全中)**。

## 证据链

1. **症状**:全部旧产物(ZDL)在 Ziddle 里跑音频块 = 1 块撞 20M 预算
   (norm5/merged/stock5 皆然);烟测(NOP 音频)6 cycles/块正常。
2. **定位**(`zdlrun --trace-hot 30000`):pc 跳到 0x3F7FFFFE(浮点位型当
   函数指针),`cur_insn_pc=0x1F6A`;寄存器组合显示调用目标是
   `Ampsim_init` 场景(arg=memR、0x4400、44100.0f)。
3. **数学**:期望目标 = TEXT_ORIG(0x7E0)+obj 偏移(0x1040)= **0x1820**;
   实际落点 = **0x1F40**;差 = +0x720 = **调用点自己的文件偏移**
   (0x728 处的分支)。第二个调用点 0x748 → 0x1F60,差同为 +0x748。
4. **代码**:`linker.py::_apply_relocs` 中
   `addend = rel['addend'] if sym['shndx'] != 0 else 0`
   (rel['addend'] = PCR_S21 时置为该指令的文件偏移)。
   该补偿的注释本意只对"cl6x 段内 CALLP 占位=从段起点计"成立;
   **跨段(.audio→.text)重定位也套用了它** → target 多加一个偏移。
   两棵树的这段代码逐字相同(用户 fork 与 2026-10 lineage 同源),
   而 themanro 已发布效果(Gyre 等)不受影响的原因待查
   (推测其成品对象在该路径上的占位约定不同;不影响本结论)。
5. **修复(第一半,两棵树各自一行,已应用)**:
   `same_sec = sym['shndx'] != 0 and sym['shndx'] == sec['idx']`
   `addend = rel['addend'] if same_sec else 0` —— 只对**同段**补偿。
6. **修复(第二半,同日续,最终块)**:`_patch_pcr_s21` 用**精确指令地址**
   计算位移,但 C674x 以**取指包基准 (pc & ~31)** 加位移——所有非 32 对齐
   调用点都偏 `(addr & 31)` 字节。实例:`.audio` 里 0xD4C 处的调用
   (`0xD4C & 31 = 12`)落到 `Ampsim_process` 入口 **前 12 字节** = 前一个
   函数的 BNOP 返回桩 → 静默无处理(短路径/零输出);更早的构建里则
   表现为随机执行/NaN。修复:`delta = (target - (instr_addr & ~31)) >> 2`。
7. **验证**:修复后 `AmpNeve_full.ZDL`(SHA256 744F786E…)音频块
   0 = 4.5k 周期、稳态 86k 周期(真实 DSP 负载),全曲 41343 块
   **NaN=0、peak 0.96/rms 0.20**,与 x86 离线渲染器(peak 0.86/rms 0.25)
   同型;matcheck 9 参数双 PASS。Reverson(AF077DC5…)同样双 PASS +
   真实音频(14k 周期/块)。

## 配套产物

- 修复版候选:`dist/AmpNeve_norm_r2.ZDL`/`norm5_r2.ZDL`(+烟测对)
- 修复前产物全部改名 `*_r1_bug.*` 留档(不删)
- `zdlrun --trace-hot/--trace-skip/--dump-io`(work/ziddle_rig/zdlrun.rs)
- 日志:work/desc/trace_run.log、trace_block1.log、audio_fixed_run.log、
  speed_probe{2,3}.log
- **探针(probes/b1on_probe/out/ 全部 15 件)与旧矩阵都是修复前产物,
  上机前必须用修复后的 fork 树重建**(脚本已在 probes/b1on_probe/)

## 修复前/后对比(同一输入)

| 工件 | 修复前 | 修复后 |
|---|---|---|
| 音频回调 1 块 | >2×10^8 周期或崩跳野地址 | 4588 cycles(首块含初始化) |
| 稳态块 | 不适用(不返回) | 1107 cycles/块 |
| matcheck | 双 PASS(init/handler 不走该路径) | 双 PASS(保持) |
