@echo off
REM Oikotie Daily Automation Windows Task Setup
REM Generated on 2025-07-21T01:11:03.374364

echo Setting up Windows Task Scheduler for Oikotie Daily Automation...

schtasks /create /tn "Oikotie Daily Automation" /tr "python \"G:\proj\oikotie\run_daily_automation.py\"" /sc daily /st 06:00 /f

echo Task created successfully!
echo The automation will run daily at 6:00 AM
pause
