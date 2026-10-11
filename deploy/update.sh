#!/bin/bash
# =====================================================================
# 一键更新脚本（Linux 服务器）
#
# 用法：ssh 登录后执行  bash /opt/app/update.sh
# 作用：本地改完代码 → git push → 服务器跑这个脚本即可完成更新
#
# ⚠️ 前置：代码已推送到 GitHub 主分支（默认 main）
# ⚠️ 注意：数据库不受本脚本影响，实验数据不会被覆盖
# ⚠️ 注意：如果本次更新涉及**修改表结构**，需先手工执行迁移 SQL，
#         项目未使用 Alembic，请参考 database/migrate_*.sql 自行编写
# =====================================================================
set -e   # 任一步失败立即停止，避免带着错误继续

APP_DIR="/opt/app/project01"
SERVICE="travel-experiment"

echo "=========================================="
echo " 开始更新  $(date '+%Y-%m-%d %H:%M:%S')"
echo "=========================================="

# --- 1. 拉取最新代码 ---
cd "$APP_DIR"
echo ">>> [1/4] 拉取最新代码..."
git pull
echo "    当前版本：$(git log --oneline -1)"

# --- 2. 更新后端依赖 ---
echo ">>> [2/4] 更新后端依赖..."
cd "$APP_DIR/backend"
source venv/bin/activate
pip install -r requirements.txt --quiet
deactivate

# --- 3. 重新构建前端（关键！不 build，Nginx 托管的还是旧产物）---
echo ">>> [3/4] 重新构建前端..."
cd "$APP_DIR/frontend"
npm install --silent
npm run build
echo "    构建产物：$(du -sh dist | cut -f1)"

# --- 4. 重启后端 ---
echo ">>> [4/4] 重启后端服务..."
sudo systemctl restart $SERVICE

echo "=========================================="
echo " 更新完成  $(date '+%Y-%m-%d %H:%M:%S')"
echo "=========================================="
echo "服务状态："
sudo systemctl status $SERVICE --no-pager | head -5
echo ""
echo "查看实时日志： sudo journalctl -u $SERVICE -f"
echo "健康检查：curl http://127.0.0.1:8000/api/health"