#!/usr/bin/env python3
"""部署自检 —— 检查线上烧录站是否配好、传全、缓存策略是否生效。

用法：
    python3 scripts/verify_deploy.py https://xiaozhi.example.com
    python3 scripts/verify_deploy.py https://xiaozhi.example.com:7275
    python3 scripts/verify_deploy.py http://localhost:8000      # 本地预览也能查

检查项：
    1. TLS 证书有效期（https 时）
    2. 关键资源的 HTTP 状态与 Content-Type
    3. 缓存响应头是否按预期生效（没生效说明 nginx 配置没贴进去）
    4. 固件是否支持范围请求（206）
    5. 固件实际大小与 config.json 里声明的是否一致

退出码：0 = 全部通过，1 = 有需要处理的问题。
"""

import argparse
import datetime
import json
import re
import socket
import ssl
import sys
import urllib.error
import urllib.parse
import urllib.request

TIMEOUT = 25
UA = {"User-Agent": "xiaozhi-flasher-verify/1.0"}

PASS, FAIL, WARN = "✓", "✗", "!"


def head(url, extra=None):
    """发 HEAD 请求，返回 (状态码, 小写 header 字典)。4xx/5xx 不抛异常。"""
    req = urllib.request.Request(url, method="HEAD", headers={**UA, **(extra or {})})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            return r.status, {k.lower(): v for k, v in r.headers.items()}
    except urllib.error.HTTPError as e:
        return e.code, {k.lower(): v for k, v in (e.headers or {}).items()}
    except Exception as e:  # noqa: BLE001
        return None, {"_error": str(e)}


def get(url, limit=None):
    req = urllib.request.Request(url, headers=UA)
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            return r.read() if limit is None else r.read(limit)
    except Exception as e:  # noqa: BLE001
        print(f"  {FAIL} 无法获取 {url}：{e}")
        return None


def check_cert(host, port):
    ctx = ssl.create_default_context()
    try:
        with socket.create_connection((host, port), TIMEOUT) as sock:
            with ctx.wrap_socket(sock, server_hostname=host) as ss:
                cert = ss.getpeercert()
                proto = ss.version()
    except ssl.SSLCertVerificationError as e:
        return [("证书", FAIL, f"验证失败：{e.verify_message or e}")]
    except Exception as e:  # noqa: BLE001
        return [("证书", WARN, f"无法建立 TLS 连接：{e}")]

    subject = dict(x[0] for x in cert.get("subject", ()))
    issuer = dict(x[0] for x in cert.get("issuer", ()))
    cn = subject.get("commonName", "?")
    org = issuer.get("organizationName") or issuer.get("commonName", "?")
    raw = cert.get("notAfter", "")
    try:
        exp = datetime.datetime.strptime(raw, "%b %d %H:%M:%S %Y %Z").replace(
            tzinfo=datetime.timezone.utc
        )
        days = (exp - datetime.datetime.now(datetime.timezone.utc)).days
        mark = PASS if days > 14 else WARN
        note = f"{cn}（{org}），{proto}，有效至 {exp:%Y-%m-%d}，剩 {days} 天"
    except ValueError:
        mark, note = WARN, f"{cn}（{org}），到期时间无法解析：{raw}"
    return [("证书", mark, note)]


def main():
    ap = argparse.ArgumentParser(description="线上烧录站部署自检")
    ap.add_argument("base", help="站点地址，如 https://xiaozhi.example.com")
    ap.add_argument("--skip-firmware", action="store_true", help="跳过固件体积比对")
    args = ap.parse_args()

    base = args.base.rstrip("/")
    parsed = urllib.parse.urlparse(base)
    host = parsed.hostname
    port = parsed.port or (443 if parsed.scheme == "https" else 80)

    print(f"\n小智烧录站 · 部署自检\n目标：{base}\n" + "─" * 68)
    problems = []

    if parsed.scheme == "https":
        print("\n[1/5] 证书")
        for name, mark, note in check_cert(host, port):
            print(f"  {mark} {name}：{note}")
            if mark != PASS:
                problems.append("证书")
    else:
        print("\n[1/5] 证书——非 https，跳过")
        print(f"  {WARN} 线上必须用 https，否则浏览器不给串口权限（localhost 例外）")

    print("\n[2/5] 关键资源")
    paths = ["/", "/index.html", "/config.json", "/css/style.css", "/js/app.js", "/js/install-button.js"]
    for p in paths:
        st, h = head(base + p)
        if st is None:
            print(f"  {FAIL} {p:<24} {h.get('_error')}")
            problems.append(p)
            continue
        ct = h.get("content-type", "—").split(";")[0]
        print(f"  {PASS if st == 200 else FAIL} {p:<24} {st}  {ct}")
        if st != 200:
            problems.append(p)

    print("\n[3/5] 缓存策略")
    expect = {
        "/": ("no-cache", False),
        "/index.html": ("no-cache", False),
        "/config.json": ("no-cache", False),
        "/css/style.css": ("no-cache", False),
        "/js/app.js": ("no-cache", False),
    }
    for p, (want, _) in expect.items():
        st, h = head(base + p)
        cc = h.get("cache-control", "")
        ok = want in cc
        print(f"  {PASS if ok else FAIL} {p:<24} {'no-cache' if ok else (cc or '（缺少 Cache-Control）')}")
        if not ok:
            problems.append("缓存策略未生效")
    nosniff = any(head(base + p)[1].get("x-content-type-options") for p in ("/js/app.js", "/"))

    cfg_raw = get(base + "/config.json")
    firmwares = []
    if cfg_raw:
        try:
            cfg = json.loads(cfg_raw)
            for fw in cfg.get("firmwares", []):
                for v in fw.get("versions", []):
                    firmwares.append((fw.get("id"), v))
        except json.JSONDecodeError as e:
            print(f"  {FAIL} config.json 不是合法 JSON：{e}")
            problems.append("config.json")

    print("\n[4/5] 固件范围请求与体积")
    if args.skip_firmware or not firmwares:
        print("  已跳过")
    for fw_id, v in firmwares:
        path = "/" + v["bin"].lstrip("./")
        st, h = head(base + path, {"Range": "bytes=0-1023"})
        rng = h.get("content-range", "")
        st206, h2 = head(base + path)
        size = int(h2.get("content-length", 0) or 0)
        declared = v.get("size", "")
        m = re.match(r"([\d.]+)\s*MB", declared or "")
        size_ok = None
        if m:
            expect_b = float(m.group(1)) * 1024 * 1024
            size_ok = abs(size - expect_b) / expect_b < 0.005
        ct = h2.get("content-type", "—").split(";")[0]
        print(f"  {v['version']}  {path}")
        print(f"      {PASS if st == 206 else FAIL} 范围请求 {'206 ' + rng if rng else '不支持（部分工具会失败）'}")
        print(f"      {PASS if ct == 'application/octet-stream' else FAIL} Content-Type {ct}")
        if size:
            note = f"{size:,} 字节"
            if size_ok is True:
                note += f"  与声明 {declared} 一致"
            elif size_ok is False:
                note += f"  {FAIL} 与声明 {declared} 不一致"
            print(f"      {PASS if size_ok is not False else FAIL} {note}")
        else:
            print(f"      {FAIL} 拿不到 Content-Length，文件可能没传全")
            problems.append(path)
        if st != 206:
            problems.append("范围请求")

    print("\n[5/5] 隐私复核")
    if firmwares:
        v = firmwares[0][1]
        req = urllib.request.Request(
            base + "/" + v["bin"].lstrip("./"),
            headers={**UA, "Range": "bytes=36864-36895"},   # NVS 分区头部
        )
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
                blob = r.read()
            wiped = all(b == 0xFF for b in blob)
            print(f"  {PASS if wiped else FAIL} NVS 起始区{'已擦除' if wiped else '仍有数据 —— 可能传了未脱敏的原始镜像！'}")
            if not wiped:
                problems.append("隐私")
        except Exception as e:  # noqa: BLE001
            print(f"  {WARN} 无法读取 NVS 区域：{e}")

    print("\n" + "─" * 68)
    if problems:
        uniq = list(dict.fromkeys(problems))
        print(f"结论：{len(uniq)} 项需要处理 → {'、'.join(uniq)}")
        if "缓存策略未生效" in uniq:
            print("\n提示：把 deploy/1panel-openresty.conf 里的内容贴进 1Panel 站点的配置文件")
            print("      （网站 → 你的站点 → 配置文件），保存后 1Panel 会自动 reload。")
            if not nosniff:
                print("      目前连 nosniff 也没有，说明该配置片段确实还没应用。")
        sys.exit(1)
    print("结论：全部通过，可以对外交付。")


if __name__ == "__main__":
    main()
