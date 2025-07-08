## Brief overview
Documentation maintenance rules for the Oikotie project establishing mandatory procedures for keeping README.md, docs/ folder, and all project documentation synchronized with codebase changes.

## README.md maintenance requirements
- README.md MUST be updated for any feature additions, removals, or significant modifications
- Installation instructions MUST reflect current dependency requirements and setup procedures
- Usage examples MUST be tested and verified before documentation updates
- API documentation references MUST match actual module interfaces and functionality
- Configuration examples MUST reflect current config.json structure and options
- System requirements MUST be updated when dependencies or minimum versions change

## docs/ folder synchronization standards
- Script documentation in docs/scripts/ MUST match actual script functionality and parameters
- Workflow documentation MUST reflect current pipeline steps and execution order
- Dashboard documentation MUST stay current with visualization capabilities
- All command examples in documentation MUST be tested and verified
- New scripts MUST have corresponding documentation created in docs/scripts/
- Deprecated scripts MUST have documentation removed or marked as deprecated

## Documentation update triggers
### Mandatory updates required for:
- New features or capabilities added to the platform
- Changes to installation requirements or setup procedures
- Modifications to command-line interfaces or script parameters
- Updates to configuration file structure or options
- Changes to API interfaces or module functionality
- New dependencies added or existing dependencies updated
- System requirements changes (Python version, browser, OS support)
- Workflow modifications or new pipeline steps

### Documentation review triggers:
- Before any public release or version tagging
- When user reports documentation-related issues
- After major refactoring or architectural changes
- When Memory Bank update is requested (comprehensive review)

## Quality standards for documentation
- **Accuracy**: All examples and instructions must be tested and working
- **Completeness**: Cover all user-facing functionality and common use cases
- **Clarity**: Use clear, concise language suitable for target audience
- **Consistency**: Maintain consistent terminology and formatting throughout
- **Currency**: Reflect current state of codebase, not planned or deprecated features
- **Accessibility**: Ensure documentation is readable and navigable

## Integration with Memory Bank workflow
- Documentation updates MUST trigger Memory Bank review when significant
- activeContext.md MUST document any documentation changes made
- progress.md MUST reflect documentation status and known gaps
- techContext.md MUST be updated when technical documentation changes
- Documentation changes count as "significant changes" for Memory Bank updates

## Documentation testing requirements
- **Installation procedures**: Test on clean environment
- **Command examples**: Verify all commands execute successfully
- **Code examples**: Ensure all code snippets are functional
- **Configuration examples**: Validate JSON syntax and effectiveness
- **Links**: Check all internal and external links are functional
- **Dependencies**: Verify all listed dependencies are actually required

## Specific file maintenance rules

### README.md critical sections requiring vigilance:
- Installation Steps section (verify commands work)
- Quick Start section (test complete workflow)
- Usage examples (validate code functionality)
- Configuration examples (ensure JSON is valid)
- System Requirements (match actual requirements)
- Script table (reflect actual available scripts)

### docs/scripts/ maintenance:
- Each script MUST have corresponding .md file
- Documentation MUST include purpose, parameters, and examples
- Dependencies and prerequisites MUST be clearly stated
- Expected outputs and side effects MUST be documented
- Error conditions and troubleshooting MUST be covered

### Jupyter notebook documentation:
- notebooks/ directory descriptions MUST be current
- Notebook purposes and usage MUST be clearly explained
- Required data files and setup MUST be documented
- Example outputs or expected results MUST be described

## Documentation workflow integration
### Development workflow:
1. Make code changes
2. Update relevant documentation immediately
3. Test documentation changes
4. Update Memory Bank if changes are significant
5. Verify documentation completeness before commit

### Task completion workflow:
1. Complete all documentation updates for the task
2. Update Memory Bank files to reflect completed work
3. Create concise commit message (≤72 characters) describing the changes
4. Commit all documentation and code changes together
5. Verify commit includes all modified files

### Release workflow:
1. Comprehensive documentation review
2. Test all examples and procedures
3. Update version references if applicable
4. Verify all links and references
5. Update Memory Bank with release documentation status

## Error prevention measures
- **Pre-commit checks**: Verify documentation changes are included
- **Regular audits**: Periodic review of documentation accuracy
- **User feedback**: Monitor for documentation-related issues
- **Automated checks**: Where possible, automate documentation validation
- **Version control**: Track documentation changes alongside code changes

## Responsibility matrix
- **Developer**: Update documentation for any code changes made
- **Reviewer**: Verify documentation changes accompany code changes
- **Maintainer**: Ensure overall documentation quality and consistency
- **User feedback**: Report documentation issues through proper channels

## Documentation debt management
- **Identify gaps**: Regular assessment of documentation completeness
- **Prioritize fixes**: Address critical documentation issues first
- **Track progress**: Monitor documentation improvement over time
- **Prevent accumulation**: Address documentation debt immediately
- **Memory Bank integration**: Document known documentation debt in progress.md

## Success metrics
- **Accuracy rate**: All documented procedures work as described
- **Completeness**: All user-facing features are documented
- **Currency**: Documentation reflects current codebase state
- **User success**: Users can successfully follow documentation
- **Issue reduction**: Fewer documentation-related support requests
