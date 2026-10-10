#!/usr/bin/env python3
"""把一个新固件登记进网站，并自动生成 manifest。

用法示例：
    python3 scripts/add_version.py \
        --firmware allinone \
        --version v1.7.0 \
        --bin firmware/firmware.bin \
        --changes "优化收音机搜台速度" \
        --changes "修复 TF 卡热插拔后不识别"

做的事情：
  1. 把 bin 归档成 firmware/<firmware-id>_<version>.bin
  2. 生成 manifests/<firmware-id>_<version>.json（单文件、偏移 0）
  3. 在 config.json 对应固件类型的 versions 列表最前面插入记录并置为 latest
  4. 刷新 cacheBust，避免 CDN 把旧固件缓存住

用 `python3 scripts/add_version.py --list` 可以列出当前所有固件类型。
"""

import argparse
import json
import re
import shutil
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "config.json"


def slug(text: str) -> str:
    return re.sub(r"[^0-9A-Za-z]+", "_", text).strip("_")


def load_config() -> dict:
    return json.loads(CONFIG.read_text(encoding="utf-8"))


def save_config(cfg: dict) -> None:
    CONFIG.write_text(json.dumps(cfg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def find_firmware(cfg: dict, key: str):
    """按 id 或名称查找固件类型。"""
    fws = cfg.get("firmwares", [])
    for i, fw in enumerate(fws):
        if fw.get("id") == key or fw.get("name") == key:
            return i, fw
    return None, None


def cmd_list(cfg: dict) -> None:
    fws = cfg.get("firmwares", [])
    if not fws:
        print("config.json 里没有配置任何固件类型。")
        return
    print("当前固件类型：")
    for fw in fws:
        vers = "、".join(v.get("version", "?") for v in fw.get("versions", [])) or "（无）"
        print(f"  {fw.get('id'):<12} {fw.get('name'):<10} 版本：{vers}")


def main() -> int:
    ap = argparse.ArgumentParser(description="登记一个新固件版本")
    ap.add_argument("--list", action="store_true", help="列出所有固件类型后退出")
    ap.add_argument("--firmware", help="固件类型 id（见 --list），只有一个时可省略")
    ap.add_argument("--version", help="版本号，例如 v1.7.0")
    ap.add_argument("--bin", help="合并好的 factory bin 路径")
    ap.add_argument("--chip", default=None, help="芯片家族，默认沿用 config.json 里的 flashing.chipFamily")
    ap.add_argument("--date", default=date.today().isoformat(), help="发布日期 YYYY-MM-DD")
    ap.add_argument("--changes", action="append", default=[], help="更新内容，可重复传入")
    ap.add_argument("--offset", default="0", help="烧录偏移，合并后的 factory bin 固定为 0")
    ap.add_argument("--improv", action="store_true", help="固件支持 Improv Wi-Fi 串口配网")
    ap.add_argument("--erase", dest="erase", action="store_true", default=True)
    ap.add_argument("--no-erase", dest="erase", action="store_false")
    args = ap.parse_args()

    cfg = load_config()

    if args.list:
        cmd_list(cfg)
        return 0

    if not (args.version and args.bin):
        ap.error("需要 --version 和 --bin（或用 --list 查看现有固件类型）")

    # 定位固件类型
    if args.firmware:
        idx, fw = find_firmware(cfg, args.firmware)
        if fw is None:
            print(f"找不到固件类型：{args.firmware}\n可用值：", file=sys.stderr)
            cmd_list(cfg)
            return 1
    else:
        fws = cfg.get("firmwares", [])
        if len(fws) != 1:
            print("config.json 里有多个固件类型，请用 --firmware 指定。", file=sys.stderr)
            cmd_list(cfg)
            return 1
        idx, fw = 0, fws[0]

    fw_id = fw.get("id") or slug(fw.get("name", "firmware")).lower()
    chip = args.chip or (cfg.get("flashing", {}).get("chipFamily") or "ESP32")

    src = Path(args.bin)
    if not src.is_file():
        print(f"找不到固件文件：{src}", file=sys.stderr)
        return 1

    ver_slug = slug(args.version)

    # 1. 归档固件
    fw_dir = ROOT / "firmware"
    if not fw_dir.is_dir():
        fw_dir.mkdir(parents=True, exist_ok=True)
    bin_name = f"{fw_id}_{ver_slug}.bin"
    bin_dest = fw_dir / bin_name
    if src.resolve() != bin_dest.resolve():
        shutil.copy2(src, bin_dest)
    size = bin_dest.stat().st_size
    if size < 128 * 1024:
        print(f"警告：{bin_name} 只有 {size / 1024:.0f} KB，看起来不像合并后的完整固件，"
              f"确认一下是不是漏了 bootloader / partitions。", file=sys.stderr)

    # 2. 生成 manifest
    manifest = {
        "name": f"{fw.get('name', '固件')}",
        "version": args.version,
        "new_install_prompt_erase": bool(args.erase),
        "builds": [
            {
                "chipFamily": chip,
                "improv": bool(args.improv),
                "parts": [
                    {"path": f"../firmware/{bin_name}", "offset": int(args.offset, 0)}
                ],
            }
        ],
    }
    man_dir = ROOT / "manifests"
    if not man_dir.is_dir():
        man_dir.mkdir(parents=True, exist_ok=True)
    man_name = f"{fw_id}_{ver_slug}.json"
    (man_dir / man_name).write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    # 3. 插入版本记录（只清理本固件类型内的 latest 标记）
    for v in fw.get("versions", []):
        v.pop("latest", None)
    entry = {
        "version": args.version,
        "date": args.date,
        "manifest": f"./manifests/{man_name}",
        "bin": f"./firmware/{bin_name}",
        "size": f"{size / 1024 / 1024:.2f} MB",
        "latest": True,
        "changes": args.changes or ["常规更新"],
    }
    fw.setdefault("versions", []).insert(0, entry)

    # 4. 刷新缓存标记
    cfg["cacheBust"] = date.today().strftime("%Y%m%d") + "02"
    save_config(cfg)

    print(f"固件类型   → {fw.get('name')}（{fw_id}）")
    print(f"固件已归档 → firmware/{bin_name}  ({size / 1024 / 1024:.2f} MB)")
    print(f"清单已生成 → manifests/{man_name}")
    print(f"版本已登记 → config.json（{args.version} 已设为 latest）")
    print(f"缓存已刷新 → {cfg['cacheBust']}")
    print()
    print("可选：把下面这行字段填进 config.json 的对应版本里，页面上就会显示校验值")
    print(f'  shasum -a 256 firmware/{bin_name}')
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
