#!/bin/bash
# =====================================================================
# 数据库定时备份脚本（Linux 服务器）
#
# 放到 /opt/backup/backup.sh，然后加 crontab：
#   7 3 * * * bash /opt/backup/backup.sh
# 每天 3:07 自动备份（避开整点，减少与其他任务撞车）
#
# 说明：
#  - 备份为纯文本 .sql，可用 psql 直接恢复
#  - 自动清理旧备份，只保留最近 30 份（40G 磁盘很容易被撑满）
#  - 备份失败会返回非 0，便于 crontab 邮件告警
# =====================================================================
set -u

# ===== 可修改配置 =====
BACKUP_DIR="/opt/backup/travel_experiment"
DB_USER="travel"
DB_HOST="127.0.0.1"
DB_NAME="travel_experiment"
KEEP_DAYS=30            # 保留最近多少份
MIN_FREE_MB=500         # 磁盘剩余低于此值(MB)则先删最旧的备份
# ====================

mkdir -p "$BACKUP_DIR"
DATE=$(date +%Y%m%d_%H%M%S)
TARGET="$BACKUP_DIR/backup_${DATE}.sql"

# 1) 检查磁盘空间：不足则先删最旧的一份再备份
FREE_MB=$(df -Pm "$BACKUP_DIR" | awk 'NR==2 {print $4}')
if [ "${FREE_MB:-0}" -lt "$MIN_FREE_MB" ]; then
    echo "[$(date '+%F %T')] 磁盘剩余 ${FREE_MB}MB < ${MIN_FREE_MB}MB，先清理最旧备份"
    ls -t "$BACKUP_DIR"/backup_*.sql 2>/dev/null | tail -n +2 | xargs -r rm -f
fi

# 2) 导出数据库
#    -Fc 为自定义压缩格式，更小且支持 pg_restore 选择性恢复
echo "[$(date '+%F %T')] 开始备份 $DB_NAME -> $TARGET"
if ! pg_dump -U "$DB_USER" -h "$DB_HOST" -d "$DB_NAME" -Fc -f "$TARGET" 2>/tmp/backup_err.txt; then
    echo "[$(date '+%F %T')] ❌ 备份失败："
    cat /tmp/backup_err.txt
    exit 1
fi

SIZE=$(du -h "$TARGET" | cut -f1)
echo "[$(date '+%F %T')] ✅ 备份完成：$TARGET（$SIZE）"

# 3) 清理旧备份，只保留最近 KEEP_DAYS 份
DELETED=$(ls -t "$BACKUP_DIR"/backup_*.sql 2>/dev/null | tail -n +$((KEEP_DAYS + 1)) | xargs -r rm -f | wc -l)
TOTAL=$(ls -1 "$BACKUP_DIR"/backup_*.sql 2>/dev/null | wc -l)
echo "[$(date '+%F %T')] 当前保留 $TOTAL 份备份（已清理 $DELETED 份）"