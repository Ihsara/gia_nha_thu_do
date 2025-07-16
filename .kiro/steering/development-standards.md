---
inclusion: always
---

# Development Standards

This file imports and consolidates the comprehensive development standards from `.clinerules/` for consistent application across all development work.

## Core Development Principles

### Testing & Validation Strategy
#[[file:.clinerules/testing-workflow.md]]

**Key Requirements:**
- **MANDATORY**: Any script >10 minutes MUST have bug tests first
- **Progressive Validation**: 10 → 100 → Full scale testing approach
- **Cost Optimization**: 10-20% time investment in testing vs pipeline failures
- **Bug Prevention**: 100% pass rate required before expensive operations

### Database Management
#[[file:.clinerules/database-management.md]]

**Critical Standards:**
- **Single DuckDB Strategy**: `data/real_estate.duckdb` only, no SQLite
- **Spatial Extensions**: PostGIS-compatible operations required
- **Schema Documentation**: Mandatory table and relationship documentation
- **Migration Procedures**: Versioned scripts with rollback plans

### Git Workflow Standards
#[[file:.clinerules/git-workflow.md]]

**Mandatory Practices:**
- **Conventional Commits**: `type(scope): description` format required
- **Feature Branches**: All work on dedicated branches
- **Task Completion**: Every task MUST end with a git commit
- **Documentation Sync**: Code and docs committed together

### Memory Bank Integration
#[[file:.clinerules/memory-bank-workflow.md]]

**Session Management:**
- **Read ALL files** at session start (not optional)
- **Hierarchical order**: projectbrief → productContext → systemPatterns → techContext → activeContext → progress
- **Update triggers**: Significant changes, user requests, context clarification
- **Documentation-first**: Complete docs before code changes

## Data Governance & Quality

### Open API Usage
#[[file:.clinerules/data-governance-open-apis.md]]

**Respectful Usage:**
- **Rate Limiting**: Max 1 request/second to open data portals
- **Database-First**: Always check local data before external calls
- **Bulk Downloads**: Prefer bulk over individual queries
- **Cache Everything**: Store all retrieved data permanently

### Progressive Validation Strategy
#[[file:.clinerules/progressive-validation-strategy.md]]

**3-Step Approach:**
1. **Small Sample (10-20)**: Proof of concept, <5 minutes
2. **Medium Scale (100-500)**: Scalability validation
3. **Full Scale**: Production readiness, ≥99.40% match rate

**Quality Gates:**
- Technical AND logical correctness required
- Manual verification of real-world sense
- Performance acceptability at each scale

## Documentation & Error Management

### Documentation Maintenance
#[[file:.clinerules/documentation-maintenance.md]]

**Synchronization Requirements:**
- **README.md**: Update for any feature changes
- **docs/ folder**: Keep script documentation current
- **Testing**: All examples must be verified working
- **Memory Bank**: Update for significant changes

### Error Documentation System
#[[file:.clinerules/error-documentation-system.md]]

**Bug Tracking Standards:**
- **Every bug documented** with root cause analysis
- **Test cases created** for all bugs to prevent regression
- **Frequency tracking** to identify patterns
- **File structure**: `docs/errors/[category]-bugs.md`

## Task Management & Handoffs

### Task Handoff Strategy
#[[file:.clinerules/new-task-handoff.md]]

**Critical Triggers:**
- **Context window >50%**: MUST initiate handoff
- **Long-running projects**: Multi-session work
- **Complex implementations**: Multiple distinct phases

**Handoff Requirements:**
- Use `ask_followup_question` tool to offer new task
- Use `new_task` tool with comprehensive context
- Include completed work, current state, next steps

### Temporary Script Execution
#[[file:.clinerules/temporary-script-execution.md]]

**When Shell Commands Fail:**
- **Location**: Always create in `tmp/` directory
- **Naming**: `{purpose}_{timestamp}.py`
- **Structure**: Standard header with purpose, usage, findings
- **Cleanup**: Delete at task end unless valuable for future

## Mandatory Reminders for Every Task

### Visualization & Output Standards
- **Output Location**: All visualization files in `output/visualization/`
- **Housekeeping**: Clean up temporary files from main directory
- **Related Data Only**: Only visualize data with listing relationships
- **Performance Focus**: Process only relevant data

### Quality Assurance Checklist
- [ ] Bug prevention tests created and passing
- [ ] Progressive validation approach followed
- [ ] Database operations use DuckDB utilities
- [ ] Documentation updated with code changes
- [ ] Git commit follows conventional format
- [ ] Memory Bank updated for significant changes
- [ ] Temporary files cleaned up
- [ ] Output files in correct directories

## Integration Patterns

### Cross-Rule Dependencies
- **Testing + Database**: All database operations must have tests
- **Git + Documentation**: All commits include doc updates
- **Memory Bank + Error Tracking**: Bug discoveries update Memory Bank
- **Progressive Validation + Testing**: Each validation step has tests

### Workflow Orchestration
1. **Session Start**: Read Memory Bank completely
2. **Planning**: Apply progressive validation strategy
3. **Implementation**: Follow testing workflow, database standards
4. **Documentation**: Update all relevant docs and Memory Bank
5. **Completion**: Git commit with conventional format
6. **Handoff**: Use task handoff tools when needed

This comprehensive development standards framework ensures consistent, high-quality development practices across all aspects of the Oikotie project.