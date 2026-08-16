# ZDL 效果模块格式

## 封装

```
NULL + SIZE(8B: header_size, elf_size)
    + INFO(48B)
    + [BCAB / CABI 扩展段]
    + TI C6000 ELF32(little-endian, ET_DYN)
```

- ELF 起始 = 20 + header_size。
- INFO 布局(最终确认):
  - +32: real_type
  - +36: fxid(u16)
  - +38: bass_flags
  - +39: sort_fx_type

## 导出符号

固件通过名字查找:`Dll_<Name>`、`Fx_<GID>_<Name>`、init/onf/edit 处理器、
`SonicStomp`、`effectTypeImageInfo`、图片与旋钮信息。

## 加载规则(安全约束)

- 保持 `memsz == filesz`,`.fardata` 保持极小。
- 不要依赖 C 运行时启动/零填充(loader 不是普通 ELF 加载器)。
- 不引入 DSBT/GOT/TLS/C++ 运行时。
- 音频回调不使用 `B14`(DP),数据须 `--mem_model:data=far` 或绝对寻址。

## 状态与音频

- `ctx[1]` 参数 float 表;`ctx[2]` 状态头;`ctx[3]` 大状态描述符;
  `ctx[4]/[5]/[6]` 干/湿/累加缓冲;`ctx[11]/[12]` magic shuttle。
- 每回调 8 样本/声道。
- 原厂 DELAY 音频入口:ZDL ELF 偏移 `0x7800`;init 偏移 `0x584`。
