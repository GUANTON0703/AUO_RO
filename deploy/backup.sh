#!/bin/sh
set -e
DB=/srv/rotxt/data/rotxt.db
DIR=/srv/rotxt/backups
mkdir -p "$DIR"
sqlite3 "$DB" ".backup '$DIR/rotxt-$(date +%F).db'"
find "$DIR" -name 'rotxt-*.db' -mtime +14 -delete
