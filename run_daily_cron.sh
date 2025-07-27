#!/bin/bash
# Oikotie Daily Automation Cron Wrapper
# Generated on 2025-07-21T01:11:03.372358

cd "G:\proj\oikotie"
export PATH="$PATH:G:\proj\oikotie/.venv/bin"

# Log start
echo "$(date): Starting daily automation" >> logs/cron.log

# Run automation
python3 "G:\proj\oikotie\run_daily_automation.py" >> logs/cron.log 2>&1

# Log completion
echo "$(date): Daily automation completed" >> logs/cron.log
