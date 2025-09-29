#!/bin/sh

touch /var/log/cron.log
touch /code/last_update_id.txt
chown -R root:root /code/last_update_id.txt

echo "Running initial workflow execution..."
python /code/app/main.py

echo "Starting cron daemon in the background..."
cron -f &

echo "Starting FastAPI server in the foreground..."
exec "$@"