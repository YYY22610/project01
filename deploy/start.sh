#!/usr/bin/env bash
# =====================================================================
# 生产启动脚本（Linux 服务器）
# 启动后端：uvicorn 单 worker，绑 127.0.0.1:8000（不暴露公网，由 nginx 本地转发）
#
# ⚠️ 关键点：必须保持「单实例 / 单 worker」。
#   提醒调度器（main.py 内每 30 秒扫描到期提醒发邮件）是进程内单协程。
#   若用 --workers N>1 或开多个进程/多台机器，会出现重复发信。
#   本平台已在代码层用「查 sent_at → 发信 → 写 sent_at」减小窗口，
#   但多实例下无行锁，无法彻底避免，故运维上必须单实例。
#
# 用法：
#   chmod +x deploy/start.sh
#   ./deploy/start.sh          # 前台运行（调试）
#   或用 systemd（见 deploy/travel-experiment.service）托管
# =====================================================================
set -euo pipefail

PROJECT_DIR="/path/to/travel-experiment-platform"
cd "$PROJECT_DIR/backend"

# 优先使用项目 venv
VENV="$PROJECT_DIR/backend/venv"
if [ -x "$VENV/bin/python" ]; then
  PY="$VENV/bin/python"
else
  PY="$(command -v python3)"
fi

export PYTHONUNBUFFERED=1

exec "$PY" -m uvicorn app.main:app \
  --host 127.0.0.1 \
  --port 8000 \
  --workers 1 \
  --log-level info
