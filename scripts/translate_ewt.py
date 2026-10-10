#!/usr/bin/env python3
"""把 esp-web-tools 的界面文案替换成中文。

背景：esp-web-tools v10 没有多语言机制，弹窗里的 Install / Erase device /
Back / Next 等都是写死在打包产物里的英文。组件是本地自托管的，所以直接对
js/ 下的打包文件做精确字符串替换。

用法：
    python3 scripts/translate_ewt.py            # 汉化（可重复运行，幂等）
    python3 scripts/translate_ewt.py --check    # 只检查，不改动

想调整译文：直接改下面 FILE_RULES 里的中文即可。

注意：
    - 只动「界面文案」。esptool 的底层日志（Hash of data verified 等）是
      排障信息，故意保留英文；Windows / Mac 这类平台名也保留。
    - 每条替换都标了预期出现次数，对不上会警告，防止误伤代码逻辑。
    - 按钮/列表项用 tag 模式（>原文<），只匹配标签之间的文本，
      避免碰到同名方法（如 ew-dialog.close()）。
"""

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# 每组：(文件通配, 替换列表)
# 替换项：(说明, 原文, 译文, 预期出现次数)
#   kind=plain : 普通子串替换
#   kind=tag   : 模板里的按钮/标题文本 >原文<，两侧允许任意空白
FILE_RULES = [
    ("install-dialog-*.js", [
        # ── 对话框标题 ──
        ("对话框标题", "Install ${this._manifest.name}", "烧录 ${this._manifest.name}", "plain", 2),

        # ── 确认烧录页 ──
        ("确认页标题", '"Confirm Installation"', '"确认烧录"', "plain", 1),
        ("确认页-已装固件句", "Your device is running", "当前设备正在运行", "plain", 1),
        ("确认页-问句", "Do you want to ${r}", "是否要${r}", "plain", 1),
        ("确认页-动词(升级)", '"update to"', '"更新到"', "plain", 1),
        ("确认页-动词(全新安装)", '"install"', '"烧录"', "plain", 1),
        ("确认页-擦除警告", "All data on the device will be erased.", "设备上的所有数据将被擦除。", "plain", 1),

        # ── 擦除询问页 ──
        ("擦除页标题", '"Erase device"', '"擦除设备"', "plain", 1),
        ("擦除页问句上半", "Do you want to erase the device before installing", "是否在烧录前擦除设备？擦除后", "plain", 1),
        ("擦除页问句下半", "? All data on the device will be lost.", " 设备上的所有数据都将丢失。", "plain", 1),
        ("擦除页复选框", "Erase device\n        </label>", "擦除设备\n        </label>", "plain", 1),

        # ── 同版本重烧页（选了同版本固件时出现）──
        ("重置页标题", '"Erase User Data"', '"清除用户数据"', "plain", 1),
        ("重置页问句", "Do you want to reset your device and erase all user data from your\n          device?",
         "是否重启设备并清除设备上的所有用户数据？", "plain", 1),

        # ── 烧录进度状态 ──
        ("进度-连接中(带省略号)", '"Connecting..."', '"连接中…"', "plain", 1),
        ("进度-连接中", '"Connecting"', '"连接中"', "plain", 1),
        ("进度-准备中(带省略号)", '"Preparing installation..."', '"正在准备安装…"', "plain", 1),
        ("进度-准备中", '"Preparing installation"', '"正在准备安装"', "plain", 1),
        ("进度-擦除中", '"Erasing"', '"正在擦除"', "plain", 1),
        ("进度-烧录中", '"Installing"', '"正在烧录"', "plain", 4),
        ("进度-收尾中", '"Wrapping up"', '"正在收尾"', "plain", 1),

        # ── 完成页与侧栏 ──
        ("完成消息", "Installation complete!", "烧录完成！", "plain", 1),
        ("失败消息", "Installation failed", "烧录失败", "plain", 1),
        ("就绪消息", "Installation prepared", "烧录准备完成", "plain", 1),
        ("清单下载失败", "Failed to download manifest", "固件清单下载失败", "plain", 1),
        ("错误页标题", 'return["Error",s`', 'return["错误",s`', "plain", 1),

        # ── 按钮与列表项（模板文本）──
        ("按钮-上一步", "Back", "上一步", "tag", 5),
        ("按钮-下一步", "Next", "下一步", "tag", 2),
        ("按钮-开始烧录", "Install", "开始烧录", "tag", 1),
        ("按钮-关闭", "Close", "关闭", "tag", 1),
        ("按钮-继续", "Continue", "继续", "tag", 1),
        ("按钮-连接", "Connect", "连接", "tag", 1),
        ("按钮-跳过", "Skip", "跳过", "tag", 1),
        ("列表-日志与控制台", "Logs & Console", "日志与控制台", "tag", 2),
        ("列表-访问设备", "Visit Device", "访问设备", "tag", 2),
        ("列表-重启设备", "Reset Device", "重启设备", "tag", 1),
        ("列表-清除用户数据", "Erase User Data", "清除用户数据", "tag", 2),
        ("列表-下载日志", "Download Logs", "下载日志", "tag", 1),
        ("列表-添加到HA", "Add to Home Assistant", "添加到 Home Assistant", "tag", 2),
        ("列表-支持开发者", "Fund Development", "支持开发者", "tag", 1),
    ]),

    ("index-*.js", [
        # 「未选择串口」提示弹窗
        ("串口弹窗标题", "No port selected", "未选择串口", "tag", 1),
        ("按钮-取消", "Cancel", "取消", "tag", 1),
        ("按钮-关闭", "Close", "关闭", "tag", 1),
        ("按钮-重试", "Try Again", "重试", "tag", 1),
        # Windows / Mac 是平台下载链接，保留英文
    ]),
]

# 允许保留英文的模板文本（平台名等）
KEEP_ENGLISH = {"Windows", "Mac", "Windows & Mac", "Linux", "iOS", "Android"}


def translate(text, rules):
    results = []
    out = text
    for name, old, new, kind, expected in rules:
        if kind == "plain":
            n = out.count(old)
            if n == 0:
                done = new in out
                results.append((name, "ok" if done else "miss",
                                "已汉化" if done else "⚠ 没有命中，检查组件版本"))
                continue
            results.append((name, "ok" if n == expected else "warn",
                            f"{n} 处" if n == expected else f"命中 {n} 次，预期 {expected} 次"))
            out = out.replace(old, new)
        else:  # tag
            pat = re.compile(r"(>)\s*" + re.escape(old) + r"\s*(<)")
            found = len(pat.findall(out))
            if found == 0:
                done = new in out
                results.append((name, "ok" if done else "miss",
                                "已汉化" if done else "⚠ 没有命中，检查组件版本"))
                continue
            results.append((name, "ok" if found == expected else "warn",
                            f"{found} 处" if found == expected else f"命中 {found} 次，预期 {expected} 次"))
            out = pat.sub(r"\g<1>" + new + r"\g<2>", out)
    return out, results


def remaining_english(text):
    left = set()
    for m in re.finditer(r">\s*\n?\s*([A-Z][A-Za-z'& .!?]{2,40})\s*\n?\s*<", text):
        s = m.group(1)
        if s not in KEEP_ENGLISH:
            left.add(s)
    return sorted(left)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="只报告，不修改文件")
    args = ap.parse_args()

    rc = 0
    any_file = False
    for pattern, rules in FILE_RULES:
        for f in sorted((ROOT / "js").glob(pattern)):
            any_file = True
            text = f.read_text(encoding="utf-8")
            new, results = translate(text, rules)

            print(f"\n{f.name}  ({len(text):,} 字节)")
            print("─" * 56)
            for name, status, detail in results:
                mark = {"ok": "✓", "warn": "!", "miss": "✗"}[status]
                print(f"  {mark} {name:<14} {detail}")
                if status == "miss":
                    rc = 1

            if args.check:
                continue

            if new != text:
                f.write_text(new, encoding="utf-8")
                print(f"  已写回，{len(text):,} → {len(new):,} 字节")
            else:
                print("  文件无变化（此前已汉化）")

            left = remaining_english(new)
            print(f"  模板残留英文：{left if left else '无'}")

    if not any_file:
        print("在 js/ 下没找到目标文件")
        return 1
    return rc


if __name__ == "__main__":
    sys.exit(main())
