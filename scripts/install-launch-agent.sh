#!/bin/bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
UV_BIN="$(command -v uv)"
PLIST="$HOME/Library/LaunchAgents/com.local.huckleberry-homepod.plist"
LOG_DIR="$HOME/Library/Logs/huckleberry-homepod"
DOMAIN="gui/$(id -u)"
SERVICE="$DOMAIN/com.local.huckleberry-homepod"

mkdir -p "$(dirname "$PLIST")" "$LOG_DIR"
cat >"$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>com.local.huckleberry-homepod</string>
  <key>ProgramArguments</key>
  <array>
    <string>$UV_BIN</string>
    <string>run</string>
    <string>--project</string>
    <string>$PROJECT_DIR</string>
    <string>hb-homepod</string>
    <string>run</string>
  </array>
  <key>WorkingDirectory</key>
  <string>$PROJECT_DIR</string>
  <key>RunAtLoad</key>
  <true/>
  <key>KeepAlive</key>
  <true/>
  <key>StandardOutPath</key>
  <string>$LOG_DIR/service.log</string>
  <key>StandardErrorPath</key>
  <string>$LOG_DIR/service-error.log</string>
</dict>
</plist>
EOF

if launchctl print "$SERVICE" >/dev/null 2>&1; then
  launchctl bootout "$SERVICE"
  for _ in 1 2 3 4 5; do
    if ! launchctl print "$SERVICE" >/dev/null 2>&1; then
      break
    fi
    sleep 1
  done
fi

for attempt in 1 2 3; do
  if launchctl bootstrap "$DOMAIN" "$PLIST"; then
    break
  fi
  if [[ "$attempt" == 3 ]]; then
    echo "后台服务注册失败；请注销并重新登录 Mac 后再运行本脚本。" >&2
    exit 1
  fi
  echo "launchd 尚未完成清理，2 秒后重试（$attempt/3）……"
  sleep 2
done

echo "已安装并启动：com.local.huckleberry-homepod"
echo "日志目录：$LOG_DIR"
