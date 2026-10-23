/* 小智固件在线烧录站 —— 页面逻辑
 * 读取 config.json 渲染页面，并把「固件类型 + 版本」对应的 manifest 交给
 * <esp-web-install-button> 去烧录。
 */
(function () {
  "use strict";

  var $ = function (id) { return document.getElementById(id); };

  var CFG = null;
  var BUST = "";
  var FW_INDEX = 0;

  function bust(url) {
    if (!url) return url;
    if (!BUST) return url;
    return url + (url.indexOf("?") === -1 ? "?" : "&") + "v=" + encodeURIComponent(BUST);
  }

  function el(tag, cls, text) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text != null) n.textContent = text;
    return n;
  }

  /* ---------------- 头部 ---------------- */
  function renderHeader(cfg) {
    var s = cfg.site || {};
    if (s.title) { document.title = s.title + " · 固件在线烧录"; $("siteTitle").textContent = s.title; }
    if (s.subtitle) $("siteSubtitle").textContent = s.subtitle;
    if (s.badge) $("brandBadge").textContent = s.badge;
    if (s.footer) $("footerText").textContent = s.footer;
  }

  /* ---------------- 设备信息 ---------------- */
  function renderProduct(cfg) {
    var p = cfg.product || {};
    if (p.name) $("productName").textContent = p.name;
    if (p.description) $("productDesc").textContent = p.description;

    var badges = $("productBadges");
    (p.badges || []).forEach(function (b) { badges.appendChild(el("span", "chip", b)); });

    if (p.image) {
      var box = $("productImage");
      box.innerHTML = "";
      var img = el("img");
      img.src = p.image;
      img.alt = p.name || "产品图";
      box.appendChild(img);
    }

    (p.links || []).forEach(function (l) {
      var a = el("a", null, l.label);
      a.href = l.url;
      a.target = "_blank";
      a.rel = "noopener";
      $("productLinks").appendChild(a);
    });

    var specs = p.specs || [];
    if (specs.length) {
      $("specCard").hidden = false;
      var grid = $("specGrid");
      specs.forEach(function (s) {
        var row = el("div", "spec-item");
        row.appendChild(el("span", "k", s.label));
        row.appendChild(el("span", "v", s.value));
        grid.appendChild(row);
      });
    }

    var tables = p.tables || [];
    if (tables.length) {
      $("tableCard").hidden = false;
      var box = $("tableBox");
      tables.forEach(function (t) {
        var block = el("div", "table-block");
        if (t.title) block.appendChild(el("div", "table-caption", t.title));
        var wrap = el("div", "table-wrap");
        var table = el("table");
        var thead = el("thead");
        var htr = el("tr");
        (t.columns || []).forEach(function (c) { htr.appendChild(el("th", null, c)); });
        thead.appendChild(htr);
        table.appendChild(thead);
        var tbody = el("tbody");
        (t.rows || []).forEach(function (r) {
          var tr = el("tr");
          r.forEach(function (cell, i) {
            tr.appendChild(el("td", i === 1 ? "mono" : null, cell));
          });
          tbody.appendChild(tr);
        });
        table.appendChild(tbody);
        wrap.appendChild(table);
        block.appendChild(wrap);
        box.appendChild(block);
      });
    }
  }

  /* ---------------- 烧录说明 ---------------- */
  function renderFlashing(cfg) {
    var f = cfg.flashing || {};
    if (f.chipFamily) {
      $("chipHint").textContent = f.chipFamily;
      $("metaChip").textContent = "芯片：" + f.chipFamily;
    }
    if (f.baudRate) $("metaBaud").textContent = "波特率：" + f.baudRate;

    var ol = $("stepList");
    (f.steps || []).forEach(function (text) {
      var li = document.createElement("li");
      li.innerHTML = text;
      ol.appendChild(li);
    });

    if (f.tips && f.tips.length) {
      $("tipsBox").hidden = false;
      var html = "<strong>常见问题</strong><ul>";
      f.tips.forEach(function (t) { html += "<li>" + t + "</li>"; });
      $("tipsBox").innerHTML = html + "</ul>";
    }
  }

  /* ---------------- 固件选择 ---------------- */
  function applyVersion(fwIdx, verIdx) {
    var fw = CFG.firmwares[fwIdx];
    var v = fw.versions[verIdx];

    $("installBtn").setAttribute("manifest", bust(v.manifest));
    $("binLink").href = bust(v.bin || v.manifest);
    $("manifestLink").href = bust(v.manifest);
    $("metaSize").textContent = "固件：" + fw.name + " " + v.version +
      (v.size ? "（" + v.size + "）" : "");

    var box = $("versionChanges");
    var items = (v.changes || []).slice();
    var html = "<strong>" + v.version + (v.date ? "　" + v.date : "") + "</strong><ul>";
    items.forEach(function (c) { html += "<li>" + c + "</li>"; });
    html += "</ul>";
    if (v.sha256) {
      html += '<div class="hash"><span>SHA256</span><code>' + v.sha256 + "</code></div>";
    }
    box.innerHTML = html;
    box.hidden = false;

    // 版本切换后回到页面顶部附近，避免用户以为没反应
    FW_INDEX = fwIdx;
  }

  function renderVersionSelect(fwIdx) {
    var fw = CFG.firmwares[fwIdx];
    var sel = $("versionSelect");
    sel.innerHTML = "";
    fw.versions.forEach(function (v, i) {
      var opt = document.createElement("option");
      opt.value = String(i);
      opt.textContent = v.version + (v.date ? "　" + v.date : "");
      sel.appendChild(opt);
    });
    var initial = 0;
    fw.versions.forEach(function (v, i) { if (v.latest) initial = i; });
    sel.value = String(initial);
    applyVersion(fwIdx, initial);
    return initial;
  }

  function renderFirmwares(cfg) {
    var list = $("firmwareList");
    var firmwares = cfg.firmwares || [];
    if (!firmwares.length) return;

    firmwares.forEach(function (fw, i) {
      var card = el("button", "fw-card");
      card.type = "button";
      card.dataset.index = String(i);

      var head = el("div", "fw-head");
      head.appendChild(el("span", "fw-name", fw.name));
      if (fw.badge) head.appendChild(el("span", "fw-badge", fw.badge));
      card.appendChild(head);

      if (fw.description) card.appendChild(el("p", "fw-desc", fw.description));

      if (fw.features && fw.features.length) {
        var feats = el("div", "fw-features");
        fw.features.forEach(function (f) { feats.appendChild(el("span", "fw-feature", f)); });
        card.appendChild(feats);
      }

      card.addEventListener("click", function () {
        Array.prototype.forEach.call(list.children, function (c) {
          c.classList.remove("is-active");
        });
        card.classList.add("is-active");
        renderVersionSelect(i);
      });

      list.appendChild(card);
    });

    // 默认选中第一个（或标记 default 的那个）
    var defIdx = 0;
    firmwares.forEach(function (fw, i) { if (fw.default) defIdx = i; });
    list.children[defIdx].classList.add("is-active");
    renderVersionSelect(defIdx);

    $("versionSelect").addEventListener("change", function () {
      applyVersion(FW_INDEX, Number($("versionSelect").value));
    });
  }

  /* ---------------- 手动刷入本地固件 ---------------- */
  // 所有 esp-web-tools 支持的芯片家族，第一项会按 config 的 chipFamily 高亮
  var CHIP_FAMILIES = [
    "ESP32-S3", "ESP32", "ESP32-S2", "ESP32-C3", "ESP32-C2",
    "ESP32-C6", "ESP32-H2", "ESP32-C5", "ESP32-P4", "ESP8266"
  ];

  var localFileUrl = null;     // 选中 .bin 的 Blob URL
  var localManifestUrl = null; // 内存中构造的 manifest 的 Blob URL

  function parseOffset(raw) {
    var s = String(raw || "").trim().toLowerCase();
    if (!s) return 0;
    var n;
    if (s.indexOf("0x") === 0) n = parseInt(s.slice(2), 16);
    else n = parseInt(s, 10);
    return isNaN(n) ? 0 : n;
  }

  function formatSize(bytes) {
    if (bytes >= 1024 * 1024) return (bytes / 1024 / 1024).toFixed(2) + " MB";
    if (bytes >= 1024) return (bytes / 1024).toFixed(1) + " KB";
    return bytes + " B";
  }

  function buildLocalManifest(file, chip, offset) {
    return {
      name: "本地固件 " + file.name,
      version: "本地",
      new_install_prompt_erase: true,
      builds: [
        {
          chipFamily: chip,
          improv: false,
          parts: [{ path: localFileUrl, offset: offset }]
        }
      ]
    };
  }

  function setupLocalFirmware(cfg) {
    var fileInput = $("localFile");
    var chipSel = $("localChip");
    var offsetInput = $("localOffset");
    var panel = $("localFlashPanel");
    var btn = $("installLocalBtn");
    if (!fileInput || !chipSel || !panel || !btn) return;

    // 填充芯片下拉：把 config 里的芯片放到最前面并默认选中
    var defaultChip = (cfg.flashing && cfg.flashing.chipFamily) || "ESP32-S3";
    var chips = CHIP_FAMILIES.slice();
    if (chips.indexOf(defaultChip) === -1) chips.unshift(defaultChip);
    chips.forEach(function (c) {
      var opt = document.createElement("option");
      opt.value = c;
      opt.textContent = c;
      chipSel.appendChild(opt);
    });
    chipSel.value = defaultChip;

    function updateChipHint() {
      $("localChipHint").textContent = chipSel.value;
      $("localMetaChip").textContent = "芯片：" + chipSel.value;
    }
    updateChipHint();
    chipSel.addEventListener("change", function () {
      updateChipHint();
      // 已选文件时，重新生成 manifest 以套用新芯片
      if (localFileUrl) refreshLocalManifest();
    });

    offsetInput.addEventListener("change", function () {
      if (localFileUrl) refreshLocalManifest();
    });

    function refreshLocalManifest() {
      var chip = chipSel.value;
      var offset = parseOffset(offsetInput.value);
      var manifest = buildLocalManifest(fileInput.files[0], chip, offset);
      var blob = new Blob([JSON.stringify(manifest)], { type: "application/json" });
      var url = URL.createObjectURL(blob);
      if (localManifestUrl) URL.revokeObjectURL(localManifestUrl);
      localManifestUrl = url;
      btn.setAttribute("manifest", url);
    }

    fileInput.addEventListener("change", function () {
      var file = fileInput.files && fileInput.files[0];
      if (!file) {
        panel.hidden = true;
        return;
      }
      if (localFileUrl) URL.revokeObjectURL(localFileUrl);
      localFileUrl = URL.createObjectURL(file);

      var chip = chipSel.value;
      var offset = parseOffset(offsetInput.value);
      var manifest = buildLocalManifest(file, chip, offset);
      var blob = new Blob([JSON.stringify(manifest)], { type: "application/json" });
      if (localManifestUrl) URL.revokeObjectURL(localManifestUrl);
      localManifestUrl = URL.createObjectURL(blob);
      btn.setAttribute("manifest", localManifestUrl);

      $("localMetaFile").textContent = "文件：" + file.name;
      $("localMetaSize").textContent = "大小：" + formatSize(file.size);
      updateChipHint();
      panel.hidden = false;
    });
  }

  /* ---------------- 环境检查 ---------------- */
  function checkSupport() {
    // 组件自身会切到 slot="unsupported" / slot="not-allowed" 的提示内容，
    // 这里只在控制台留线索，方便排查。
    if (!window.isSecureContext) {
      console.warn("[flasher] 非安全上下文，Web Serial 不可用：请用 https 或 localhost 打开");
    } else if (!("serial" in navigator)) {
      console.warn("[flasher] 当前浏览器不支持 Web Serial，请用桌面版 Chrome / Edge / Firefox");
    }
  }

  fetch("./config.json", { cache: "no-cache" })
    .then(function (r) {
      if (!r.ok) throw new Error("HTTP " + r.status);
      return r.json();
    })
    .then(function (cfg) {
      CFG = cfg;
      BUST = cfg.cacheBust || "";
      renderHeader(cfg);
      renderProduct(cfg);
      renderFlashing(cfg);
      renderFirmwares(cfg);
      setupLocalFirmware(cfg);
      checkSupport();
    })
    .catch(function (err) {
      $("siteTitle").textContent = "配置读取失败";
      $("siteSubtitle").textContent =
        "无法加载 config.json（" + err.message + "）。请用本地服务器打开本页面，" +
        "不要直接双击 index.html 文件。";
    });
})();
