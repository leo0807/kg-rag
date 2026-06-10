#!/bin/bash
# cron-backup.sh — 定时备份包装脚本（由 cron 调用）
# 安装定时任务：crontab -e
#   0 2 * * * /path/to/kg-rag/scripts/cron-backup.sh >> /var/log/kg-rag-backup.log 2>&1
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$SCRIPT_DIR/.."
BACKUP_ROOT="$ROOT_DIR/backups"
RETENTION_DAYS=${BACKUP_RETENTION_DAYS:-7}
ALERT_WEBHOOK="${WECOM_WEBHOOK:-${DINGTALK_WEBHOOK:-}}"

cd "$ROOT_DIR"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"; }

send_alert() {
  local msg="$1"
  if [[ -n "$ALERT_WEBHOOK" ]]; then
    curl -s -X POST "$ALERT_WEBHOOK" \
      -H "Content-Type: application/json" \
      -d "{\"msgtype\":\"text\",\"text\":{\"content\":\"[KG-RAG备份告警] $msg\"}}" \
      >/dev/null 2>&1 || true
  fi
}

# ── 执行备份 ────────────────────────────────────────────────────────
log "定时备份开始..."
if "$SCRIPT_DIR/backup.sh" "$BACKUP_ROOT"; then
  log "备份成功"
else
  log "备份失败！"
  send_alert "每日备份失败，请检查服务器状态"
  exit 1
fi

# ── 清理旧备份（保留最近 N 天）────────────────────────────────────
log "清理 ${RETENTION_DAYS} 天前的备份..."
if [[ -d "$BACKUP_ROOT" ]]; then
  find "$BACKUP_ROOT" -maxdepth 1 -type d -mtime "+$RETENTION_DAYS" \
    -exec echo "删除旧备份: {}" \; \
    -exec rm -rf {} + 2>/dev/null || true
fi

BACKUP_COUNT=$(find "$BACKUP_ROOT" -maxdepth 1 -type d | wc -l)
log "当前备份数量: $((BACKUP_COUNT - 1))"
log "定时备份完成"

# ── 安装提示 ───────────────────────────────────────────────────────
# 如果作为独立命令运行则显示安装帮助
if [[ "${CRON_MODE:-}" != "1" ]]; then
  echo ""
  echo "提示：将以下行添加到 crontab（crontab -e）即可启用自动备份："
  echo "  0 2 * * * CRON_MODE=1 $SCRIPT_DIR/cron-backup.sh >> /var/log/kg-rag-backup.log 2>&1"
fi
