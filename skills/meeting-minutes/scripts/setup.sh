#!/usr/bin/env bash
# meeting-minutes 一键安装脚本
# 用法: bash ~/.hermes/skills/productivity/meeting-minutes/scripts/setup.sh
set -e

VENV="$HOME/funasr-env"
SKILL_DIR="$(cd "$(dirname "$0")/.." && pwd)"

echo "=== meeting-minutes 环境安装 ==="
echo ""

# 1. 系统依赖
echo "[1/3] 检查系统依赖..."
if ! command -v python3 &>/dev/null; then
    echo "  ✗ 需要 python3"
    exit 1
fi
echo "  python3: $(python3 --version 2>&1)"

if ! command -v ffmpeg &>/dev/null; then
    echo "  ✗ 需要 ffmpeg"
    echo ""
    echo "  安装方法:"
    echo "    Ubuntu/Debian:  sudo apt install ffmpeg"
    echo "    macOS:          brew install ffmpeg"
    echo "    Conda:          conda install ffmpeg"
    echo ""
    exit 1
fi
echo "  ffmpeg: OK"

# 2. 创建虚拟环境 + 安装依赖
echo "[2/3] 准备虚拟环境 ($VENV)..."
if [ -d "$VENV" ]; then
    echo "  已存在，跳过创建"
else
    python3 -m venv "$VENV"
    echo "  创建完成"
fi

echo "[3/3] 安装 Python 依赖..."
"$VENV/bin/pip" install --quiet --upgrade pip
"$VENV/bin/pip" install --quiet funasr numpy scikit-learn scipy soundfile onnxruntime
echo "  funasr=$("$VENV/bin/pip" show funasr 2>/dev/null | grep Version | awk '{print $2}')"
echo "  完成"

echo ""
echo "首次转录时 FunASR 会自动下载模型 (~3GB)，无需手动操作。"
echo ""

# 验证
echo "=== 验证 ==="
if "$VENV/bin/python3" -c "import funasr; print(f'  FunASR {funasr.__version__} ✓')" 2>/dev/null; then
    echo ""
    echo "=== 安装完成 ==="
    echo "直接告诉 Hermes Agent 录音路径即可使用，无需手动运行脚本。"
else
    echo "  ✗ FunASR 导入失败，请检查错误信息"
    exit 1
fi
