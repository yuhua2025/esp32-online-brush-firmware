#!/usr/bin/env bash
# 把编译产物合并成一个可以直接在线烧录的 factory bin（单文件、偏移 0）
#
# 用法：
#   ./scripts/merge_firmware.sh --pio                     # 自动从 .pio/build 里找
#   ./scripts/merge_firmware.sh --pio --env esp32-c3-devkitm-1
#   ./scripts/merge_firmware.sh --arduino ./MySketch      # Arduino IDE 导出编译文件后
#   ./scripts/merge_firmware.sh --chip esp32c3 --app app.bin --bootloader bl.bin \
#                               --partitions pt.bin --boot-app0 boot_app0.bin
#
# 依赖：pip install esptool

set -euo pipefail

CHIP="esp32c3"
FLASH_MODE="dio"
FLASH_FREQ="80m"
FLASH_SIZE="4MB"
OUT="firmware/firmware.bin"
MODE=""
SRC=""
ENV=""

APP=""
BOOTLOADER=""
PARTITIONS=""
BOOT_APP0=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --pio)        MODE="pio"; shift ;;
    --arduino)    MODE="arduino"; SRC="${2:-}"; shift 2 ;;
    --env)        ENV="${2:-}"; shift 2 ;;
    --chip)       CHIP="${2:-}"; shift 2 ;;
    --app)        APP="${2:-}"; shift 2 ;;
    --bootloader) BOOTLOADER="${2:-}"; shift 2 ;;
    --partitions) PARTITIONS="${2:-}"; shift 2 ;;
    --boot-app0)  BOOT_APP0="${2:-}"; shift 2 ;;
    --out)        OUT="${2:-}"; shift 2 ;;
    --flash-mode) FLASH_MODE="${2:-}"; shift 2 ;;
    --flash-freq) FLASH_FREQ="${2:-}"; shift 2 ;;
    --flash-size) FLASH_SIZE="${2:-}"; shift 2 ;;
    -h|--help)    sed -n '2,14p' "$0"; exit 0 ;;
    *) echo "未知参数：$1" >&2; exit 1 ;;
  esac
done

# ESP32 系列 bootloader 的烧录偏移不一样：只有经典 ESP32 在 0x1000，其余都在 0x0
case "$CHIP" in
  esp32|esp32s2) BOOTLOADER_OFFSET="0x1000" ;;
  *)             BOOTLOADER_OFFSET="0x0" ;;
esac

if [[ "$MODE" == "pio" ]]; then
  BUILD_ROOT=".pio/build"
  [[ -d "$BUILD_ROOT" ]] || { echo "找不到 $BUILD_ROOT，请在 PlatformIO 项目根目录运行" >&2; exit 1; }
  if [[ -z "$ENV" ]]; then
    ENV="$(ls "$BUILD_ROOT" | head -n 1)"
    echo "未指定 --env，自动使用：$ENV"
  fi
  D="$BUILD_ROOT/$ENV"
  APP="$D/firmware.bin"
  BOOTLOADER="$D/bootloader.bin"
  PARTITIONS="$D/partitions.bin"
  # boot_app0.bin 来自 Arduino 框架包
  BOOT_APP0="$(find "$HOME/.platformio/packages" -name boot_app0.bin 2>/dev/null | head -n 1 || true)"
elif [[ "$MODE" == "arduino" ]]; then
  [[ -n "$SRC" && -d "$SRC" ]] || { echo "请用 --arduino <编译输出目录> 指定路径" >&2; exit 1; }
  APP="$(find "$SRC" -maxdepth 1 -name '*.ino.bin' | head -n 1 || true)"
  BOOTLOADER="$(find "$SRC" -maxdepth 1 -name '*.ino.bootloader.bin' | head -n 1 || true)"
  PARTITIONS="$(find "$SRC" -maxdepth 1 -name '*.ino.partitions.bin' | head -n 1 || true)"
  BOOT_APP0="$(find "$HOME/Library/Arduino15" "$HOME/.arduino15" -name boot_app0.bin 2>/dev/null | head -n 1 || true)"
fi

for f in "$APP" "$BOOTLOADER" "$PARTITIONS"; do
  if [[ -z "$f" || ! -f "$f" ]]; then
    echo "缺少必要文件：${f:-<未找到>}" >&2
    echo "提示：Arduino IDE 请先用 菜单 → 项目 → 导出已编译的二进制文件" >&2
    exit 1
  fi
done

mkdir -p "$(dirname "$OUT")"

PARTS=("$BOOTLOADER_OFFSET" "$BOOTLOADER" "0x8000" "$PARTITIONS")
[[ -n "$BOOT_APP0" && -f "$BOOT_APP0" ]] && PARTS+=("0xe000" "$BOOT_APP0")
PARTS+=("0x10000" "$APP")

# esptool v4 用 merge_bin，v5 起改为 merge-bin，这里两个都兼容
run_esptool() {
  esptool --chip "$CHIP" merge-bin \
    -o "$OUT" \
    --flash-mode "$FLASH_MODE" \
    --flash-freq "$FLASH_FREQ" \
    --flash-size "$FLASH_SIZE" \
    "${PARTS[@]}" 2>/dev/null \
  || esptool --chip "$CHIP" merge_bin \
    -o "$OUT" \
    --flash-mode "$FLASH_MODE" \
    --flash-freq "$FLASH_FREQ" \
    --flash-size "$FLASH_SIZE" \
    "${PARTS[@]}"
}

if ! command -v esptool >/dev/null 2>&1; then
  echo "未安装 esptool，请先执行：pip install esptool" >&2
  exit 1
fi

run_esptool

echo
echo "合并完成 → $OUT"
ls -lh "$OUT"
echo
echo "下一步："
echo "  python3 scripts/add_version.py --version v1.0.1 --bin \"$OUT\" --chip $CHIP"
