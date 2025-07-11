## Brief overview
Git workflow rules for Python professional development establishing mandatory procedures for version control, branch management, commit practices, and code organization in the Oikotie project and all future Python projects.

## Git workflow standards
- **Feature branches**: All new features MUST be developed on dedicated feature branches (feature/description-name)
- **Commit frequency**: Commit work incrementally with logical, atomic changes
- **Commit messages**: Use conventional commits format: type(scope): description
- **Code review**: All changes MUST go through proper review process before merging
- **Clean history**: Use interactive rebase to clean up commit history before merging
- **Documentation commits**: Documentation updates MUST be committed with related code changes

## Branch naming conventions
### Mandatory branch prefixes:
- `feature/`: New features or enhancements (feature/polygon-monitoring-workflow)
- `fix/`: Bug fixes and issue resolution (fix/spatial-join-match-rate)
- `docs/`: Documentation-only changes (docs/monitoring-workflow-guide)
- `refactor/`: Code refactoring without functionality changes
- `test/`: Test additions or improvements
- `chore/`: Maintenance tasks, dependency updates, tooling

### Branch naming rules:
- Use lowercase with hyphens for separation
- Be descriptive but concise (max 50 characters)
- Include issue number when applicable: feature/123-polygon-visualization
- Branch from main/master for features, from develop for collaborative work

## Commit message standards
### Conventional commit format (MANDATORY):
```
type(scope): description

[optional body]

[optional footer]
```

### Commit types:
- **feat**: New features or capabilities
- **fix**: Bug fixes and issue resolution
- **docs**: Documentation changes only
- **style**: Code style changes (formatting, missing semicolons, etc.)
- **refactor**: Code changes that neither fix bugs nor add features
- **test**: Adding or updating tests
- **chore**: Maintenance tasks, dependency updates
- **perf**: Performance improvements
- **ci**: CI/CD pipeline changes

### Commit message examples:
```bash
feat(spatial): implement enhanced polygon monitoring workflow
fix(database): correct column names in boundary data queries
docs(monitoring): add comprehensive workflow documentation
refactor(visualization): extract polygon conversion to separate class
test(spatial-join): add validation tests for match rate criteria
chore(deps): update shapely to latest version for geometry processing
```

## File organization and staging
### Staging practices:
- **Atomic commits**: Stage related changes together in logical units
- **Separate concerns**: Documentation changes in separate commits from code changes
- **Exclude generated files**: Use .gitignore for logs, outputs, temporary files
- **Include configuration**: Commit configuration files that affect behavior

### Pre-commit requirements:
- **Code formatting**: Run black/autopep8 before committing Python code
- **Linting**: Address all critical linting issues before commit
- **Documentation sync**: Ensure documentation reflects code changes
- **Test validation**: Run relevant tests before committing

## Development workflow integration
### Task completion workflow:
1. **Create feature branch**: `git checkout -b feature/task-description`
2. **Implement changes**: Make incremental commits as work progresses
3. **Update documentation**: Commit documentation updates with related code
4. **Prepare for merge**: Clean up commit history, ensure tests pass
5. **Create commit summary**: Write comprehensive commit message
6. **MANDATORY TASK COMPLETION COMMIT**: Every completed task MUST end with a git commit
7. **Push and review**: Push branch and create pull request if applicable

### Mandatory task completion commit requirements:
- **EVERY TASK**: Must end with a git commit regardless of task size or scope
- **Commit message format**: Use conventional commits with clear task description
- **Include all changes**: All modified files from the task must be staged and committed
- **Documentation updates**: Memory Bank updates and documentation changes included
- **Descriptive messages**: Commit message should clearly describe what was accomplished
- **Atomic commits**: Each task should result in one comprehensive, well-structured commit

### Memory Bank integration:
- **Significant changes**: Any change that affects Memory Bank MUST include git context
- **Branch tracking**: Document current branch and pending merges in activeContext.md
- **Change history**: Include relevant commit hashes in Memory Bank updates
- **Release preparation**: Coordinate Memory Bank updates with git tagging

## Project-specific git practices
### Oikotie project requirements:
- **Data files**: Never commit large database files or processed datasets
- **Configuration**: Commit config templates, not sensitive configuration
- **Outputs**: Exclude visualization files, logs, and temporary processing files
- **Documentation**: Keep docs/ folder synchronized with code changes

### File inclusion/exclusion rules:
```gitignore
# Generated files
*.html
logs/
output/
*.pyc
__pycache__/

# Data files
*.db
*.duckdb
data/*.csv
data/*.json

# IDE and temp files
.vscode/settings.json
*.tmp
*.log

# Include configuration templates
!config/config.example.json
!.clinerules/
!memory-bank/
```

## Quality control standards
### Pre-merge checklist:
- [ ] All commits follow conventional commit format
- [ ] Code is properly formatted and linted
- [ ] Documentation is updated and synchronized
- [ ] Tests pass (if applicable)
- [ ] Memory Bank is updated for significant changes
- [ ] .gitignore excludes all generated/temporary files
- [ ] Commit history is clean and logical

### Code review requirements:
- **Self-review**: Always review your own changes before committing
- **Documentation review**: Ensure documentation accurately reflects changes
- **Impact assessment**: Consider effects on other parts of the system
- **Memory Bank impact**: Update Memory Bank for significant architectural changes

## Git hooks and automation
### Recommended pre-commit hooks:
```bash
# Install pre-commit framework
pip install pre-commit

# Configure hooks for Python projects
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/psf/black
    rev: 23.1.0
    hooks:
      - id: black
  - repo: https://github.com/pycqa/flake8
    rev: 6.0.0
    hooks:
      - id: flake8
```

### Automated checks:
- **Formatting**: Automatic code formatting on commit
- **Linting**: Static analysis and style checking
- **Documentation**: Verify documentation completeness
- **File exclusions**: Prevent accidental commit of generated files

## Release and tagging practices
### Version tagging:
- **Semantic versioning**: Use MAJOR.MINOR.PATCH format
- **Release branches**: Create release branches for version preparation
- **Tag annotations**: Include comprehensive release notes in tag messages
- **Memory Bank snapshots**: Coordinate releases with Memory Bank updates

### Release workflow:
1. **Prepare release branch**: `git checkout -b release/v1.2.0`
2. **Update documentation**: Ensure all docs reflect current state
3. **Update Memory Bank**: Comprehensive Memory Bank review and update
4. **Create release commit**: `chore(release): prepare v1.2.0 release`
5. **Tag release**: `git tag -a v1.2.0 -m "Release v1.2.0: Enhanced polygon monitoring"`
6. **Merge and deploy**: Merge to main and push tags

## Integration with task handoff workflow
### New task creation requirements:
- **Git status**: Document current branch, uncommitted changes, pending merges
- **Commit context**: Include relevant commit hashes and branch information
- **Merge status**: Note any pending merges or conflicts to be resolved
- **Release coordination**: Consider impact on upcoming releases or versions

### Task handoff git context (MANDATORY):
```markdown
## Git Status and Context

### Current Branch Information:
- **Active Branch**: feature/polygon-monitoring-workflow
- **Base Branch**: main
- **Commits Ahead**: 5 commits ready for merge
- **Uncommitted Changes**: Documentation updates in docs/
- **Pending Files**: 3 new files, 2 modified files staged

### Recent Commits:
- `abc1234`: feat(spatial): implement enhanced polygon monitoring workflow
- `def5678`: docs(monitoring): add comprehensive workflow documentation
- `ghi9012`: fix(database): correct column names in boundary queries

### Next Git Actions Required:
- [ ] Commit current documentation updates
- [ ] Clean up commit history with interactive rebase
- [ ] Prepare pull request for feature branch merge
- [ ] Update Memory Bank before merge
- [ ] Create release tag after successful merge
```

## Error prevention and recovery
### Common git issues prevention:
- **Accidental commits**: Use .gitignore to prevent committing generated files
- **Large files**: Check file sizes before adding to repository
- **Sensitive data**: Never commit API keys, passwords, or personal data
- **Conflict resolution**: Always test code after resolving merge conflicts

### Recovery procedures:
- **Wrong commits**: Use `git reset` or `git revert` appropriately
- **Large file cleanup**: Use git filter-branch or BFG Repo-Cleaner
- **History cleanup**: Interactive rebase for commit history organization
- **Branch recovery**: Use reflog to recover accidentally deleted branches

This git workflow ensures professional development practices, proper version control, and seamless integration with project documentation and Memory Bank management.
