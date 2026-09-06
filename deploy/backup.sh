#!/bin/sh
set -e

DB=/srv/rotxt/data/rotxt.db
DIR=/srv/rotxt/backups
KEEP_DAYS=14

mkdir -p "$DIR"
# sqlite3 online .backup：對執行中的 db 安全，不會撈到寫一半的狀態
sqlite3 "$DB" ".backup '$DIR/rotxt-$(date +%F).db'"
find "$DIR" -name 'rotxt-*.db' -mtime +"$KEEP_DAYS" -delete
