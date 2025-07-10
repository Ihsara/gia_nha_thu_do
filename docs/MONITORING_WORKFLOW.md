# Property Polygon Processing - Monitoring Workflow

This document describes the enhanced monitoring workflow for the property polygon spatial join processing, which addresses the critical 0.07% match rate issue identified in the original implementation.

## Overview

The monitoring workflow provides comprehensive tracking and logging for long-running polygon processing tasks, ensuring you can monitor progress, troubleshoot issues, and validate results effectively.

## Files Created

### Core Processing Script
- **`create_property_polygon_visualization_with_monitoring.py`**: Enhanced version with comprehensive monitoring, logging, and validation

### Monitoring Tools
- **`start_monitoring_session.sh`**: Bash script to start processing in a tmux session
- **`monitor_progress.py`**: Real-time progress monitoring script
- **`logs/current_session.json`**: Current session information and monitoring commands
- **`logs/progress_*.json`**: Real-time progress tracking
- **`logs/checkpoint_*.json`**: Processing checkpoints for resumable operations
- **`logs/property_polygon_processing_*.log`**: Detailed processing logs

## Monitoring Commands

### Start Processing with Monitoring
```bash
# Method 1: Direct execution with logging
uv run python create_property_polygon_visualization_with_monitoring.py

# Method 2: Using tmux session (recommended for long-running processes)
bash start_monitoring_session.sh
```

### Monitor Progress in Real-time
```bash
# Monitor progress continuously
python monitor_progress.py

# Check current session info
cat logs/current_session.json

# Tail log files
tail -f logs/property_polygon_processing_*.log

# Check progress file
cat logs/progress_*.json

# Monitor memory usage
ps -p <PID> -o pid,ppid,cmd,%mem,%cpu,time
```

### Using PowerShell (Windows)
```powershell
# Monitor memory usage
Get-Process python | Where-Object {$_.CPU -gt 0} | Format-Table Id,Name,CPU,WorkingSet

# Check log files
Get-Content logs\property_polygon_processing_*.log -Tail 10 -Wait

# Check session status
Get-Content logs\current_session.json | ConvertFrom-Json
```

## Progress Tracking

### Processing Stages
1. **loading_listings**: Loading property listings with coordinates
2. **loading_boundaries**: Loading Helsinki boundary data (188,142 records)
3. **creating_polygons**: Converting LineString boundaries to polygons
4. **spatial_join**: Matching listings to polygons
5. **visualization**: Creating final HTML map

### Progress Information
Each stage provides:
- Current/total items processed
- Percentage completion
- Processing rate (items/second)
- Estimated time to completion (ETA)
- Memory usage tracking
- Success/failure rates

## Success Criteria Validation

### Automated Validation Checks
The script automatically validates against these success criteria:

1. **Match Rate**: ≥80% of listings should be matched to polygons
2. **No Giant Markers**: Largest marker should have <100 listings
3. **Geographic Distribution**: Should create >10 polygon groups

### Validation Results Display
Results are shown in:
- Console output with ✅/❌ indicators
- HTML visualization validation panel
- Final checkpoint data
- Log file summary

## Files Structure

```
g:/proj/oikotie/
├── create_property_polygon_visualization_with_monitoring.py
├── start_monitoring_session.sh
├── monitor_progress.py
├── logs/
│   ├── current_session.json          # Active session info
│   ├── progress_YYYYMMDD_HHMMSS.json # Real-time progress
│   ├── checkpoint_YYYYMMDD_HHMMSS.json # Processing checkpoints
│   └── property_polygon_processing_YYYYMMDD_HHMMSS.log # Detailed logs
└── property_polygon_visualization_monitored_YYYYMMDD_HHMMSS.html # Output
```

## Error Handling and Recovery

### Checkpoint System
- Automatic checkpoints saved at each stage completion
- Progress preserved for recovery if process interrupted
- Checkpoint files contain stage data and statistics

### Error Monitoring
- Detailed error logging with stack traces
- Memory usage tracking to prevent out-of-memory issues
- Processing rate monitoring to detect performance issues

### Recovery Options
```bash
# Check last checkpoint
cat logs/checkpoint_*.json

# Review error logs
grep -i error logs/property_polygon_processing_*.log

# Monitor system resources
top -p <PID>
```

## Performance Monitoring

### Memory Usage
- Real-time memory tracking
- Peak memory usage recording
- Memory growth rate monitoring

### Processing Rates
- Items processed per second
- Stage-specific performance metrics
- ETA calculations based on current rate

### System Integration
- Process ID tracking
- System resource monitoring commands
- Kill commands for emergency stops

## Validation and Results

### Expected Improvements
Based on the full dataset processing (188,142 boundaries vs. 10,000 limit):
- **Match Rate**: From 0.07% → ≥80%
- **Polygon Groups**: From 3 total → Hundreds/thousands
- **Unmatched Marker**: From 8,094 listings → <1,000 listings
- **Geographic Distribution**: Proper distribution across Helsinki

### HTML Validation Panel
The generated HTML includes a validation panel showing:
- Total listings processed
- Match rate percentage
- Number of polygon groups created
- Largest group size
- Processing time and memory usage
- Success criteria pass/fail status

## Troubleshooting

### Common Issues
1. **High Memory Usage**: Monitor with `ps` command, consider reducing batch sizes
2. **Slow Processing**: Check processing rates in progress file
3. **Low Match Rates**: Review boundary data types and conversion success rates
4. **Process Hanging**: Check log files for error messages

### Monitoring Commands for Troubleshooting
```bash
# Check if process is still active
ps -p <PID>

# Monitor resource usage
top -p <PID>

# Check latest log entries
tail -20 logs/property_polygon_processing_*.log

# Check progress file for stuck stage
cat logs/progress_*.json | jq '.stage, .percentage'
```

## Integration with Project Workflow

### Before Running
1. Ensure database is accessible
2. Verify sufficient disk space for logs
3. Check system memory availability

### After Completion
1. Validate results in HTML visualization
2. Check success criteria in validation panel
3. Review logs for any warnings or errors
4. Update project documentation with results

This monitoring workflow ensures comprehensive tracking and validation of the property polygon processing, providing full visibility into the critical spatial join improvements.
