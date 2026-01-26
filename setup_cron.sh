#!/bin/bash
# Install Sentinel Weekly Evolution Cron Job

CRON_CMD="0 0 * * 0 /Users/macbookpro/Downloads/bot_project/weekly_evolution.sh >> /Users/macbookpro/Downloads/bot_project/cron_evolution.log 2>&1"

# Check if job already exists
(crontab -l 2>/dev/null | grep -F "$CRON_CMD") && echo "✅ Cron Job already exists." && exit 0

# Add job
(crontab -l 2>/dev/null; echo "$CRON_CMD") | crontab -
echo "✅ Cron Job installed successfully."
crontab -l
