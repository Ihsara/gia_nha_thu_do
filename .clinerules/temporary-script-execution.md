## Brief overview
Mandatory workflow for temporary script execution when shell commands fail, establishing procedures for quick code checks, data investigation, and debugging through temporary Python files.

## Temporary Script Execution Workflow

### When to Use Temporary Scripts
- Shell command execution fails or is unavailable
- Quick data investigation and validation needed
- Code snippets for debugging database queries, file operations, or data analysis
- Rapid prototyping of code solutions before implementation
- Verification of data structures, schemas, or API responses

### Mandatory Workflow Steps

#### Step 1: Create Temporary Script
- **Location**: Always create in `tmp/` directory
- **Naming Convention**: `{purpose}_{timestamp}.py` 
- **Examples**: 
  - `data_check_20250711_104900.py`
  - `db_schema_investigation_20250711_104900.py`
  - `building_validation_20250711_104900.py`

#### Step 2: Script Structure Requirements
```python
#!/usr/bin/env python3
"""
Purpose: [Clear description of what this script does]
Created: [Timestamp]
Usage: uv run python tmp/{script_name}.py
"""

# Required imports
import sys
from pathlib import Path

def main():
    """Main execution function"""
    print(f"🔧 {purpose} - Started")
    print("=" * 50)
    
    try:
        # Investigation/check code here
        pass
        
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)
    
    print(f"✅ {purpose} - Completed")

if __name__ == "__main__":
    main()
```

#### Step 3: Execute and Document
- **Execute**: `uv run python tmp/{script_name}.py`
- **Document results**: Copy key findings to task documentation
- **Save useful patterns**: Keep for reference in future tasks

#### Step 4: Cleanup Policy
- **During task**: Keep all tmp scripts for reference and iteration
- **End of task**: Delete temporary files unless they provide value for future tasks
- **Documentation**: Always document useful patterns and findings

### Documentation Standards

#### Script Header Requirements
```python
"""
INVESTIGATION PURPOSE: Quick database schema check
RELATED TASK: Dashboard refactoring and database consolidation
FINDINGS: [Document key discoveries]
USAGE PATTERN: [Note if this pattern is reusable]
CREATED: 2025-07-11 10:49
"""
```

#### Results Documentation
- **Key findings**: Always document important discoveries
- **Error patterns**: Note any errors encountered and solutions
- **Reusable code**: Identify code that could be useful in future tasks
- **Performance notes**: Document execution time and resource usage

### Temporary Script Categories

#### Database Investigation Scripts
- **Schema analysis**: Table structures, relationships, indexes
- **Data validation**: Record counts, data quality checks
- **Migration testing**: Test database changes before implementation
- **Query optimization**: Test query performance and results

#### File System Analysis Scripts
- **Directory structure**: Analyze project organization
- **File content checks**: Validate file formats, data integrity
- **Size analysis**: Check file sizes, storage usage
- **Permission validation**: Verify file access and permissions

#### Data Processing Validation Scripts
- **Sample data testing**: Quick checks on small datasets
- **Format validation**: Test data parsing and conversion
- **Algorithm testing**: Validate processing logic before full implementation
- **Performance benchmarking**: Quick performance assessments

### Integration with Main Workflow

#### Before Major Changes
- **Create validation script** to test assumptions
- **Run data checks** to understand current state
- **Test migration logic** before applying to full dataset

#### During Development
- **Incremental testing** with small scripts
- **Debug specific issues** with focused investigation scripts
- **Validate results** at each development step

#### Documentation Integration
- **Update Memory Bank** with key findings from temporary scripts
- **Reference useful patterns** in main codebase documentation
- **Note reusable components** for future development

### File Management Rules

#### Directory Structure
```
tmp/
├── data_checks/          # Database and data validation scripts
├── file_analysis/        # File system investigation scripts  
├── debugging/           # Bug investigation and debugging scripts
├── prototyping/         # Quick prototypes and proof of concepts
└── archive/            # Completed scripts kept for reference
```

#### Naming Conventions
- **Purpose prefix**: Indicate the type of investigation
- **Timestamp suffix**: Ensure unique names and track creation time
- **Descriptive middle**: Clear indication of what the script does

Examples:
- `schema_investigate_database_structure_20250711_104900.py`
- `data_validate_building_matches_20250711_104900.py`
- `debug_polygon_processing_error_20250711_104900.py`
- `prototype_enhanced_dashboard_20250711_104900.py`

### Quality Standards

#### Code Quality
- **Clear documentation**: Purpose, usage, and findings
- **Error handling**: Proper exception handling and error reporting
- **Clean output**: Formatted, readable results
- **Reusable functions**: Structure for potential reuse

#### Execution Standards
- **Fast execution**: Scripts should complete quickly (< 5 minutes)
- **Minimal dependencies**: Use standard libraries when possible
- **Resource efficient**: Avoid memory-intensive operations
- **Safe operations**: No destructive operations on important data

### Success Metrics

#### Effectiveness Measures
- **Problem resolution**: Quick identification and solution of issues
- **Development speed**: Faster debugging and validation cycles
- **Code quality**: Better understanding before implementing solutions
- **Knowledge retention**: Documented patterns for future reference

#### Documentation Quality
- **Findable**: Clear naming and organization for future reference
- **Useful**: Practical code and findings that can be reused
- **Complete**: Full context and results documented
- **Actionable**: Clear next steps and recommendations

## Integration with Git Workflow

### Temporary Script Git Handling
- **Never commit** temporary scripts to main repository
- **Add tmp/ to .gitignore** to prevent accidental commits
- **Document patterns** in permanent codebase when useful
- **Archive valuable scripts** outside main repository if needed

### Documentation Commit Standards
- **Include findings** in commit messages when relevant
- **Reference investigation** in pull request descriptions
- **Update documentation** with validated patterns and solutions
- **Note testing approach** used during development

This workflow ensures rapid development cycles while maintaining proper documentation and code quality standards.
