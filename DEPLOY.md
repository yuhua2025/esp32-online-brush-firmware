# 部署速查

纯静态站点，**不需要后端、不需要构建，也不需要 PHP**。
文件全在 `js/` `css/` `manifests/` `firmware/` 里，服务器只要能返回文件就行。
（只有 WordPress / Halo / Typecho 这类需要解释器的程序才要装 PHP。）
整个目录原样上传即可。

---

## 1. 解压

```bash
unzip xiaozhi-flasher-full-20261008.zip
cd esp-web-flasher
```

> 如果你拿到的是 `-src-` 源码包（不含固件），把 `.bin` 放进 `firmware/`、
> 放进 `manifests/`，或直接跑一遍 `scripts/add_version.py` 登记版本即可。

---

## 2. 上传前先在本地验一遍

```bash
python3 serve.py
# 浏览器打开 http://localhost:8000
```

插上设备点烧录按钮，能走完流程再上传。`localhost` 属于安全上下文，
本地 http 也能调起串口，方便排查问题——**不要跳过这步直接上线**。

---

## 3. 上传（任选一种）

### A. 1Panel + OpenResty（自己的服务器，国内常用）

**不需要装 PHP。** OpenResty 本身就是 nginx，只负责把文件发出去，静态站用不上解释器。

1. **建站**：网站 → 创建网站 → 类型选 **静态网站**（不要选「运行环境」）。
   填域名、代号（就是站点目录名），确认创建。
2. **放文件**：把包里的内容放到站点根目录 —— 以创建页面上显示的目录为准，
   常见是 `/opt/1panel/www/sites/<域名>/index`（部分版本是
   `/opt/1panel/apps/openresty/openresty/www/sites/<代号>/index`）。
   用 1Panel 的**文件管理器**上传 zip → 在线解压 → 把 `esp-web-flasher/` 里的
   **内容**（不是这个目录本身）移进 `index/`，最后 `index/index.html` 能直接打开才算对。
3. **配响应头**：网站的 `_headers` 文件 nginx 不认，要把
   `deploy/1panel-openresty.conf` 里的内容贴进站点配置文件（网站 → 配置文件），
   否则固件不会走强缓存、`config.json` 可能被缓存导致烧到旧固件。
4. **上 HTTPS**：网站 → 你的站点 → HTTPS → 申请 Let's Encrypt 证书，
   并打开**强制 HTTPS**。Web Serial 必须安全上下文，http 下按钮点了没反应。
5. **放行端口**：1Panel 防火墙放行 80 / 443；如果是云服务器，
   还要在云厂商控制台的**安全组**里再放行一次（两层都要）。

> 域名解析（A 记录指向服务器公网 IP）要先做好，否则证书签发会失败。
> 用 HTTP 验证方式申请证书要求 80 端口外部可达。

### B. Cloudflare Pages / Netlify

把 `esp-web-flasher` 目录直接拖进控制台。目录里的 `_headers` 会被自动识别，
固件走强缓存、清单实时——这两个平台不用手工配 nginx 规则。

### C. Vercel / GitHub Pages

```bash
git init && git add . && git commit -m "init"
# 推到仓库后在平台里开启即可，无需构建命令
```

### D. 对象存储 + CDN（阿里云 OSS / 腾讯云 COS / S3）

整目录上传，注意两件事：

- `.bin` 的 `Content-Type` 要是 `application/octet-stream`
- 开启 HTTPS 访问（CDN 默认有证书）

---

## 4. 上线后自检

一条命令跑完所有检查（证书、Content-Type、缓存头、范围请求、固件体积、隐私）：

```bash
python3 scripts/verify_deploy.py https://你的域名
```

有输出 `✗` 就是有问题，脚本会把该改哪儿一并提示出来。手动核对的话看这几条：

- [ ] 用 `https://` 打开，地址栏无安全警告
- [ ] 点烧录按钮**能弹出串口选择框**（弹不出来 = 不是 HTTPS）
- [ ] 直接访问固件地址返回 200，例如 `https://你的域名/firmware/xiaozhi_s3_allinone_v1.6.0.bin`
- [ ] 直接访问清单返回 200，例如 `https://你的域名/manifests/allinone_v1_6_0.json`
- [ ] 页面能正常显示中文、版本列表能切换

任何一条不通过，先看浏览器控制台的 Network 面板确认是 404 还是跨域。

---

## 5. 以后换固件

```bash
python3 scripts/add_version.py --firmware allinone --version v1.7.0 \
    --bin 你的新固件.bin --changes "更新说明一"
```

把新增的 `firmware/*.bin` 和 `manifests/*.json` 以及改动过的 `config.json`
一起重新上传即可，**不用重传全部旧固件**。

---

## 关键约束

| 项 | 说明 |
| --- | --- |
| 必须 HTTPS | Web Serial 的安全上下文限制，没有绕过办法 |
| iOS 不支持 | iPhone / iPad 全部浏览器都不行，只能电脑操作 |
| 单文件大小 | 三合一固件 16 MB，注意托管平台的单文件上限 |
| 同域最省事 | 固件和页面放同一个域名，就不用配 CORS |
| 目录别拆 | `js/` 里组件靠动态 `import()` 加载，26 个文件必须一起传 |
