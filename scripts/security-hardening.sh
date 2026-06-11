#!/bin/bash
# I6.2: Apply security hardening to the host OS (CentOS/RHEL/Ubuntu).
set -euo pipefail

echo "=== KG-RAG 安全加固 ==="

# ── 检测发行版 ────────────────────────────────────────────────────────────────
if [ -f /etc/redhat-release ]; then
    PKG_MGR="yum"
    OS_FAMILY="rhel"
elif [ -f /etc/debian_version ]; then
    PKG_MGR="apt-get"
    OS_FAMILY="debian"
else
    echo "⚠ 不支持的操作系统，跳过包安装"
    PKG_MGR=""
    OS_FAMILY="unknown"
fi

# ── 1. 关闭不必要服务 ─────────────────────────────────────────────────────────
echo "--- 关闭不必要服务 ---"
for svc in telnet rsh rlogin tftp finger chargen daytime; do
    systemctl stop    "$svc" 2>/dev/null || true
    systemctl disable "$svc" 2>/dev/null || true
done
echo "✓ 不必要服务已禁用"

# ── 2. 防火墙规则 ─────────────────────────────────────────────────────────────
echo "--- 配置防火墙 ---"
if command -v firewall-cmd &>/dev/null; then
    # firewalld (RHEL/CentOS)
    firewall-cmd --permanent --set-default-zone=drop
    firewall-cmd --permanent --add-port=22/tcp
    firewall-cmd --permanent --add-port=80/tcp
    firewall-cmd --permanent --add-port=443/tcp
    firewall-cmd --reload
elif command -v ufw &>/dev/null; then
    ufw default deny incoming
    ufw default allow outgoing
    ufw allow 22/tcp
    ufw allow 80/tcp
    ufw allow 443/tcp
    ufw --force enable
fi
echo "✓ 防火墙已配置"

# ── 3. SSH 加固 ───────────────────────────────────────────────────────────────
echo "--- SSH 加固 ---"
SSHD_CONF="/etc/ssh/sshd_config"
if [ -f "$SSHD_CONF" ]; then
    cp "$SSHD_CONF" "${SSHD_CONF}.backup.$(date +%Y%m%d)"
    sed -i 's/^#\?PermitRootLogin.*/PermitRootLogin no/'          "$SSHD_CONF"
    sed -i 's/^#\?PasswordAuthentication.*/PasswordAuthentication no/' "$SSHD_CONF"
    sed -i 's/^#\?X11Forwarding.*/X11Forwarding no/'              "$SSHD_CONF"
    sed -i 's/^#\?MaxAuthTries.*/MaxAuthTries 3/'                 "$SSHD_CONF"
    sed -i 's/^#\?ClientAliveInterval.*/ClientAliveInterval 300/' "$SSHD_CONF"
    systemctl reload sshd 2>/dev/null || true
    echo "✓ SSH 已加固（禁用 root 登录、密码登录）"
fi

# ── 4. fail2ban ───────────────────────────────────────────────────────────────
echo "--- 安装 fail2ban ---"
if [ -n "$PKG_MGR" ] && ! command -v fail2ban-client &>/dev/null; then
    $PKG_MGR install -y fail2ban 2>/dev/null || echo "⚠ fail2ban 安装失败，请手动安装"
fi

if command -v fail2ban-client &>/dev/null; then
    cat > /etc/fail2ban/jail.local <<'FAIL2BAN'
[DEFAULT]
bantime  = 3600
findtime = 600
maxretry = 5

[sshd]
enabled = true
FAIL2BAN
    systemctl enable fail2ban
    systemctl restart fail2ban
    echo "✓ fail2ban 已配置"
fi

# ── 5. 内核安全参数 ───────────────────────────────────────────────────────────
echo "--- 内核安全参数 ---"
cat >> /etc/sysctl.conf <<'SYSCTL'

# KG-RAG security hardening
net.ipv4.tcp_syncookies = 1
net.ipv4.conf.all.rp_filter = 1
net.ipv4.conf.all.accept_redirects = 0
net.ipv4.conf.all.send_redirects = 0
net.ipv4.icmp_echo_ignore_broadcasts = 1
kernel.dmesg_restrict = 1
fs.suid_dumpable = 0
SYSCTL
sysctl -p 2>/dev/null || true
echo "✓ 内核参数已加固"

# ── 6. 禁用 core dump ─────────────────────────────────────────────────────────
echo "* hard core 0" >> /etc/security/limits.conf 2>/dev/null || true

echo ""
echo "✓ 安全加固完成"
echo "  ⚠ 请重新测试 SSH 连接确认未锁定，然后退出旧会话"
