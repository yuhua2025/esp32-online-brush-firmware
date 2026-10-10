#!/usr/bin/env python3
"""本地预览服务器。

Web Serial 要求页面处于「安全上下文」：
  - http://localhost 视为安全上下文，可以直接用（推荐）
  - 用局域网 IP 从手机/另一台电脑访问时必须走 HTTPS

用法：
    python3 serve.py                 # http://localhost:8000
    python3 serve.py --port 9000
    python3 serve.py --https         # 自签名证书，用于局域网/手机测试
"""

import argparse
import http.server
import socket
import ssl
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


class Handler(http.server.SimpleHTTPRequestHandler):
    extensions_map = {
        **http.server.SimpleHTTPRequestHandler.extensions_map,
        ".bin": "application/octet-stream",
        ".json": "application/json; charset=utf-8",
        ".js": "text/javascript; charset=utf-8",
    }

    def __init__(self, *a, **kw):
        super().__init__(*a, directory=str(ROOT), **kw)

    def end_headers(self):
        # 本地调试时禁用缓存，避免改了 config.json 看不到效果
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def log_message(self, fmt, *args):
        sys.stderr.write("  %s\n" % (fmt % args))


def lan_ip() -> str:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


def ensure_cert(cert: Path, key: Path, ip: str) -> None:
    if cert.exists() and key.exists():
        return
    print("正在生成自签名证书 ...")
    subprocess.run(
        [
            "openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes",
            "-keyout", str(key), "-out", str(cert), "-days", "365",
            "-subj", "/CN=esp-web-flasher",
            "-addext", f"subjectAltName=DNS:localhost,IP:127.0.0.1,IP:{ip}",
        ],
        check=True,
        capture_output=True,
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--https", action="store_true", help="启用 HTTPS（自签名）")
    args = ap.parse_args()

    httpd = http.server.ThreadingHTTPServer(("0.0.0.0", args.port), Handler)
    scheme = "http"

    if args.https:
        cert = ROOT / ".cert" / "cert.pem"
        key = ROOT / ".cert" / "key.pem"
        cert.parent.mkdir(exist_ok=True)
        try:
            ensure_cert(cert, key, lan_ip())
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            print(f"证书生成失败：{e}\n请确认系统已安装 openssl。", file=sys.stderr)
            return 1
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.load_cert_chain(cert, key)
        httpd.socket = ctx.wrap_socket(httpd.socket, server_side=True)
        scheme = "https"
        print("\n浏览器会提示证书不受信任，选择「继续访问」即可。\n")

    print(f"服务已启动，根目录：{ROOT}")
    print(f"  本机访问   {scheme}://localhost:{args.port}")
    if args.https:
        print(f"  局域网访问 {scheme}://{lan_ip()}:{args.port}")
        print("  （局域网调试需要手机与电脑在同一 Wi-Fi 下）")
    print("\n按 Ctrl+C 停止\n")

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
