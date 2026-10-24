# 小智 AI 智能聊天机器人 · 固件在线烧录站

纯静态站点：用户插上 USB 线、点一下按钮，固件就写进设备了。
没有后端，固件不经过任何服务器中转，全部在浏览器里完成。

底层是 [esp-web-tools](https://github.com/esphome/esp-web-tools)（WLED / Tasmota / ESPHome
官方安装器都在用），在此基础上做了中文化和多固件类型管理。

**功能一览**
- 浏览器内一键烧录：插线 → 选固件 → 点按钮，无需安装任何工具
- 多固件 / 多版本管理：三合一固件、标准固件（dayu-star）可切换，版本变更与 SHA256 实时展示
- 手动烧录本地固件：支持自选 `.bin` 文件离线烧录，不经过任何服务器
- 驱动下载：页头提供 Windows / macOS 的 CH340/CH341 串口驱动直链
- 设备信息卡：产品图、规格参数、分区布局一览
- 源码跳转：页脚一键打开本项目 GitHub 仓库

---

## 一、当前收录的固件

| 固件类型 | 版本 | 大小 | 日期 | 说明 |
| --- | --- | --- | --- | --- |
| 三合一固件 | v1.6.0 | 16.00 MB | 2025-12-12 | 小智 + 收音机 + TF 卡音乐，三应用独立分区 |
| 标准固件（dayu-star） | v2.5.2 | 9.69 MB | 2026-10-23 | dayu-star 主板专用，已内置 Wi-Fi 配网，单文件镜像 |

两者均为 **ESP32-S3**、16 MB Flash、单文件镜像、烧录偏移 `0x0`。
站点会自动识别芯片型号，两种固件在「第一步 · 选择固件」里切换、共用一个烧录按钮。

页头「驱动下载」提供 Windows / macOS 的 CH340/CH341 串口驱动直链，
首次烧录用到的电脑若识别不到串口，先装好对应驱动。

---

## 二、⚠️ 发布前必读：整盘镜像会泄露设备隐私

**如果你是从自己的设备上 `read_flash` 导出的完整 16 MB 镜像，它一定包含 NVS 分区，
而 NVS 里存着你的 Wi-Fi 密码和账号密钥。直接发布 = 把你家网络和设备身份一起交出去。**

这不是猜测。本次处理的三合一固件，实测在 NVS 里发现了：

- 家庭 Wi-Fi 的 **SSID 与明文密码**
- 设备 UUID 和 `mqtt.xiaozhi.me` 的 **客户端密钥**
- 上报过的**公网 IP**
- 板子 MAC 地址

所以站点里放的 `xiaozhi_s3_allinone_v1.6.0.bin` 是**已经擦除 NVS 的版本**
（原始文件在你自己的目录里，没有被动过）。

以后每次导出新镜像，都先跑一遍检查：

```bash
# 只检查，不改文件
python3 scripts/sanitize_dump.py --in 你的镜像.bin --report-only

# 确认要发布后，生成擦除 NVS 的脱敏版
python3 scripts/sanitize_dump.py --in 你的镜像.bin --out clean.bin
```

> 擦除 NVS 后，设备首次启动会回到「等待配网」状态，用户需要重新连一次 Wi-Fi。
> 这正是发布固件应有的行为。
>
> `otadata` 分区记录 OTA 槽位状态，**三合一固件靠它决定开机进哪个应用**，
> 所以默认**不擦**。标准固件如果不需要保留槽位状态，可以加 `--wipe nvs,otadata`。

---

## 三、目录结构

```
esp-web-flasher/
├── index.html              页面骨架（含 <esp-web-install-button>）
├── config.json             ★ 站点全部内容（固件 / 驱动 / 设备信息 / 页脚链接）都在这里改
├── CNAME                   GitHub Pages 自定义域名（xiaozhi.515166.xyz）
├── css/style.css           样式
├── js/
│   ├── install-button.js   esp-web-tools 组件入口
│   ├── app.js              页面渲染 + 固件/版本切换
│   └── （其余 25 个 js）   组件的动态 import 依赖，别删
├── manifests/              固件清单，每个型号+版本一个
├── firmware/               固件本体
├── Drive/                  CH340/CH341 串口驱动（win/CH341SER.ZIP、mac/CH341SER_MAC_V1_8.zip）
├── img/                    产品图（product.jpg）与原始素材
├── scripts/
│   ├── sanitize_dump.py    ★ 检查 / 擦除整盘镜像里的隐私数据
│   ├── merge_firmware.sh   把编译产物合并成可在线烧录的单文件
│   ├── add_version.py      登记新版本：归档固件 + 生成清单 + 更新页面
│   ├── verify_deploy.py    ★ 部署后自检线上站点（证书 / 响应头 / 固件完整性）
│   └── translate_ewt.py    ★ 汉化 esp-web-tools 弹窗文案（映射表可改，幂等可重跑）
├── serve.py                本地预览服务器
├── DEPLOY.md               部署速查（上线那几步）
├── deploy/
│   └── 1panel-openresty.conf   1Panel / OpenResty 的响应头配置片段
└── _headers                Netlify / Cloudflare Pages 用的响应头配置
```

`js/` 里是 esp-web-tools 的完整打包产物。组件内部用 `import()` 动态加载各芯片的
stub flasher，所以**必须整个目录一起部署**，不能只留 `install-button.js`。

---

## 四、本地预览

```bash
python3 serve.py
# 打开 http://localhost:8000
```

`localhost` 被浏览器视为安全上下文，所以本地 **http 也能调起串口**。
线上部署则必须是 HTTPS。

手机上测试（手机和电脑连同一个 Wi-Fi）：

```bash
python3 serve.py --https      # 自动生成自签名证书
```

---

## 五、加一个新版本

```bash
# 1. 合并固件（如果手上已经是单文件镜像，跳过这步）
./scripts/merge_firmware.sh --pio --env esp32-s3-devkitc-1 --chip esp32s3

# 2. 确认没有隐私数据
python3 scripts/sanitize_dump.py --in .pio/build/esp32-s3-devkitc-1/firmware.bin --report-only

# 3. 登记版本
python3 scripts/add_version.py \
  --firmware allinone \
  --version v1.7.0 \
  --bin .pio/build/esp32-s3-devkitc-1/firmware.bin \
  --changes "优化收音机搜台速度" \
  --changes "修复 TF 卡热插拔不识别"
```

`--firmware` 就是 `config.json` 里 `firmwares[].id`，用 `--list` 可以查看：

```bash
python3 scripts/add_version.py --list
```

这一条命令会：归档固件 → 生成 `manifests/allinone_v1_7_0.json` → 把新版本插到
对应固件类型的列表顶部并标记为 latest → 刷新 `cacheBust` 缓存标记。
另一个固件类型的版本不受影响。

> **单文件镜像必须烧到偏移 0。** 浏览器端不会在烧录时实时 patch flash 参数，
> 所以要把 bootloader / 分区表 / app 用 `esptool merge-bin` 合成一份。
> 注意 ESP32 系列里只有经典 ESP32 的 bootloader 在 `0x1000`，S3 / C3 / C6 都在 `0x0`。
>
> 如果芯片同时有原生 USB（CDC）和外置 UART 桥的版本，可以在 manifest 的 build 里
> 加 `"serialType": "cdc"` 或 `"serialType": "uart"`，组件会按实际连接方式自动选固件。

---

## 六、部署

任意静态托管都行，整个目录传上去即可：

- **Cloudflare Pages / Netlify / Vercel**：拖目录，仓库里的 `_headers` 自动生效
- **GitHub Pages**：推到仓库后开启 Pages；根目录 `CNAME` 已绑定自定义域名 `xiaozhi.515166.xyz`
- **对象存储 + CDN**：给 `.bin` 设置 `Content-Type: application/octet-stream`

| 要求 | 说明 |
| --- | --- |
| 必须 HTTPS | Web Serial 的安全上下文限制，没有绕过的办法 |
| 同域或 CORS | 固件若放在别的域名，那台服务器要返回 `Access-Control-Allow-Origin` |
| 换固件要破缓存 | `add_version.py` 会自动刷新 `cacheBust` 查询串，否则 CDN 会继续发旧固件 |

单文件超过 25 MB 时注意托管平台的限制，三合一固件 16 MB 在安全范围内。

---

## 七、常见问题

**浏览器里找不到串口？**
换一根**数据线**（很多线只能充电）。ESP32-S3 的原生 USB 口认不到的话，
换用板子上的 UART 口（CH340 / CP2102）。还是不行就按住 BOOT 键点一下 RESET 再松开，
强制进入下载模式。

**烧录失败或校验不过？**
把 `config.json` 里的 `baudRate` 从 `921600` 依次降到 `460800`、`115200`。
波特率越高越快，对线材和 USB 芯片质量要求越高。

**iOS 能用吗？**
不能。iOS 上所有浏览器都不支持 Web Serial，必须用电脑。

**烧完之后还要做什么？**
设备重启后会开一个 `Xiaozhi-XXXX` 热点，用手机连上去配网，然后按屏幕提示激活即可。

**能不能保留原来的配网信息不重新配网？**
可以，但前提是这份固件不对外发布。用 `sanitize_dump.py` 时指定空的 `--wipe`
或直接使用未经处理的原始镜像即可——**但请不要把带 NVS 的镜像放到公网上**。
