#!/bin/sh
set -eu

if [ ! -f /app/config/config.json ]; then
  echo "未找到 /app/config/config.json。请先将 config/config.example.json 复制为 config/config.json 并按需修改后，再启动容器。"
  exit 1
fi

exec "$@"
