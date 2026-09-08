#!/bin/sh
# 從本機把目前 commit 推到 J1900 並重建容器。
# 用法：sh deploy/push.sh
set -e
HOST=root@10.0.4.33
APP=/srv/rotxt/app
git archive --format=tar HEAD | ssh "$HOST" "rm -rf $APP && mkdir -p $APP && tar -x -C $APP"
ssh "$HOST" "cd $APP && docker build -t rotxt:latest . && cd /srv/rotxt && docker compose up -d && docker image prune -f"
ssh "$HOST" "sleep 3 && curl -sf 172.17.0.1:8010/health && echo ' <- OK'"
