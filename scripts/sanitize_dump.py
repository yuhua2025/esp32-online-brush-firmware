#!/usr/bin/env python3
"""检查并脱敏 ESP32 整盘 Flash 镜像。

从设备 read_flash 导出的完整镜像里会带 NVS 分区，其中通常含有：
  - 已保存的 Wi-Fi SSID 与明文密码
  - 设备 UUID、MQTT/服务端密钥
  - 上传过的公网 IP、板子 MAC

这些东西一旦发布到公网就等于把设备身份和家里的网络一起交出去了，
所以在把镜像放到网站上之前，务必先跑一遍这个脚本。

用法：
    # 只检查，不改文件
    python3 scripts/sanitize_dump.py --in dump.bin --report-only

    # 擦除 NVS（恢复出厂空白），输出脱敏版
    python3 scripts/sanitize_dump.py --in dump.bin --out clean.bin

    # 同时擦除 NVS 和 otadata（otadata 记录 OTA 槽位状态，按需再擦）
    python3 scripts/sanitize_dump.py --in dump.bin --out clean.bin --wipe nvs,otadata
"""

import argparse
import hashlib
import re
import struct
import sys
from pathlib import Path

PT_MAGIC = b"\xaa\x50"
PT_TYPES = {0: "app", 1: "data"}
PT_SUBTYPES = {
    (1, 0): "otadata",
    (1, 1): "phy",
    (1, 2): "nvs",
    (1, 3): "coredump",
    (1, 4): "nvs_keys",
    (1, 0x81): "fat",
    (1, 0x82): "spiffs",
    (1, 0x83): "littlefs",
}
SENSITIVE_KEYS = (
    "ssid", "passwd", "password", "pswd", "psk", "token", "secret",
    "key", "uuid", "client_id", "username", "endpoint", "ip",
)


def find_partition_table(data: bytes, search_from: int = 0x8000, span: int = 0x2000):
    """在常见位置找分区表，返回 [(name, type, subtype, offset, size)]。"""
    for base in range(search_from, search_from + span, 0x1000):
        if data[base:base + 2] != PT_MAGIC:
            continue
        parts = []
        for i in range(64):
            ent = data[base + i * 32: base + i * 32 + 32]
            if len(ent) < 32 or ent[:2] != PT_MAGIC:
                break
            ptype, psub = ent[2], ent[3]
            off, size = struct.unpack_from("<II", ent, 4)
            name = ent[12:28].split(b"\x00")[0].decode("utf-8", "replace")
            parts.append((name, ptype, psub, off, size))
        if parts:
            return base, parts
    return None, []


def strings_in(blob: bytes, minlen: int = 5):
    return [s.decode("utf-8", "replace") for s in re.findall(rb"[\x20-\x7e]{%d,}" % minlen, blob)]


def main() -> int:
    ap = argparse.ArgumentParser(description="检查并脱敏 ESP32 整盘镜像")
    ap.add_argument("--in", dest="src", required=True, help="输入镜像")
    ap.add_argument("--out", dest="dst", help="输出脱敏镜像（不填则只检查）")
    ap.add_argument("--wipe", default="nvs", help="要擦除的分区名，逗号分隔，默认 nvs")
    ap.add_argument("--report-only", action="store_true", help="只报告，不写文件")
    args = ap.parse_args()

    src = Path(args.src)
    if not src.is_file():
        print(f"找不到文件：{src}", file=sys.stderr)
        return 1
    data = bytearray(src.read_bytes())

    if data[:1] != b"\xe9":
        print("警告：文件头不是 0xE9，这可能不是一个完整的固件镜像。", file=sys.stderr)

    pt_off, parts = find_partition_table(data)
    if not parts:
        print("没能解析出分区表。整盘镜像的分区表通常在 0x8000。", file=sys.stderr)
        return 1

    cid, = struct.unpack_from("<H", data, 12)
    chips = {0: "ESP32", 2: "ESP32-S2", 5: "ESP32-C3", 9: "ESP32-S3",
             12: "ESP32-C2", 13: "ESP32-C6", 16: "ESP32-H2", 18: "ESP32-P4"}
    print(f"文件      {src.name}  ({len(data):,} 字节 / {len(data)/1024/1024:.2f} MB)")
    print(f"芯片      {chips.get(cid, '未知')} (chip_id={cid})")
    print(f"分区表    @ 0x{pt_off:06X}")
    print()
    print(f"{'分区':<12}{'类型':<12}{'起始':<12}{'大小':<12}")
    print("-" * 50)
    for name, ptype, psub, off, size in parts:
        label = PT_SUBTYPES.get((ptype, psub), f"{ptype}/{psub}")
        print(f"{name:<12}{label:<12}0x{off:06X}    0x{off+size:06X}")

    # 扫描敏感信息
    print()
    print("=" * 56)
    print("敏感信息扫描")
    print("=" * 56)
    leaks_found = False
    for name, ptype, psub, off, size in parts:
        if (ptype, psub) not in ((1, 2), (1, 0)):   # 只查 nvs / otadata
            continue
        blob = bytes(data[off:off + size])
        if all(b == 0xFF for b in blob):
            print(f"[{name}] 空白，无数据 ✓")
            continue
        found = strings_in(blob)
        leaks_found = True
        if not found:
            used = sum(1 for b in blob if b != 0xFF)
            print(f"[{name}] 非空（{used} 个非 0xFF 字节，不含可读文本，"
                  f"属于设备运行状态，是否擦除取决于固件设计）")
            continue
        print(f"[{name}] 非空，共 {len(found)} 条可读串 —— NVS 属于设备个人状态，建议整体擦除：")
        for s in found[:40]:
            shown = s if len(s) <= 56 else s[:53] + "..."
            mark = "  ⚠" if any(k in s.lower() for k in SENSITIVE_KEYS) else ""
            print(f"    {shown}{mark}")
        if len(found) > 40:
            print(f"    ... 其余 {len(found) - 40} 条已省略")

    if not leaks_found:
        print("\n未发现残留数据，可以直接发布。")

    if args.report_only or not args.dst:
        if leaks_found and not args.report_only:
            print("\n（未指定 --out，仅做检查，未修改任何文件）")
        return 0

    # 执行擦除
    targets = [t.strip() for t in args.wipe.split(",") if t.strip()]
    by_name = {n: (o, s) for n, _, _, o, s in parts}
    print()
    print("=" * 56)
    print("擦除")
    print("=" * 56)
    for t in targets:
        if t not in by_name:
            print(f"  ! 分区 {t} 不存在，跳过")
            continue
        off, size = by_name[t]
        before = sum(1 for b in data[off:off + size] if b != 0xFF)
        data[off:off + size] = b"\xff" * size
        print(f"  ✓ {t} @ 0x{off:06X} 已擦除（清除 {before} 个非空字节）")

    out = Path(args.dst)
    out.write_bytes(bytes(data))
    print()
    print(f"已写出 {out}  ({out.stat().st_size:,} 字节)")
    print(f"SHA256 {hashlib.sha256(bytes(data)).hexdigest()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
