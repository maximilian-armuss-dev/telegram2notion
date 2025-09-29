#!/bin/sh

touch /var/log/cron.log
touch /code/processed_update_ids.json
chown -R root:root /code/processed_update_ids.json

echo "Running initial workflow execution..."
python /code/app/main.py

echo "Starting cron daemon in the background..."
cron -f &

echo "Starting FastAPI server in the foreground..."
exec "$@"