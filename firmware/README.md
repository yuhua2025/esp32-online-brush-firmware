# firmware/

存放会被烧进设备的**单文件镜像**（factory bin）。

| 文件 | 对应固件 | 说明 |
| --- | --- | --- |
| `xiaozhi_s3_allinone_v1.6.0.bin` | 三合一 | 16.00 MB，**已擦除 NVS**，可安全发布 |
| `xiaozhi_s3_standard_v2.0.5.bin` | 标准固件 | 9.52 MB，NVS 本身为空 |

## 发布前的强制检查

从设备 `read_flash` 导出的整盘镜像里，NVS 分区会带着 Wi-Fi 明文密码、
设备 UUID 和服务端密钥。**发布前必须跑一遍：**

```bash
python3 scripts/sanitize_dump.py --in 你的镜像.bin --report-only
```

确认有敏感数据后生成脱敏版：

```bash
python3 scripts/sanitize_dump.py --in 你的镜像.bin --out firmware/clean.bin
```

再用 `scripts/add_version.py` 归档，不要直接把脱敏结果改名丢进这个目录，
否则 `config.json` 里的路径和 sha256 会对不上。

## 自行合并固件

从编译产物生成单文件镜像：

```bash
pip install esptool

# PlatformIO
./scripts/merge_firmware.sh --pio --env esp32-s3-devkitc-1 --chip esp32s3
```

或手工合并（以 ESP32-S3 为例）：

```bash
esptool --chip esp32s3 merge-bin -o firmware/merged.bin \
  --flash-mode dio --flash-freq 80m --flash-size 16MB \
  0x0     bootloader.bin \
  0x8000  partitions.bin \
  0xe000  boot_app0.bin \
  0x10000 app.bin \
  0x800000 assets.bin
```

要点：

- 合并结果必须从 **偏移 0** 开始，manifest 里只写一条 `offset: 0` 就够了。
- `--flash-size` 要按实际容量填（本项目是 `16MB`）。
- 如果用了 OPI Flash（部分 S3 模组），`--flash-mode` 改成 `dout`。
- 归档时不要一直用 `merged.bin` 这个名字，让 `add_version.py` 按
  `<固件类型>_<版本>.bin` 命名，避免新旧版本互相覆盖。
