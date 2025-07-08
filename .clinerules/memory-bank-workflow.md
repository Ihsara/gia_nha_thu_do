## Brief overview
Memory Bank workflow rules specific to the Oikotie project and any projects using the Memory Bank documentation system. These guidelines establish mandatory procedures for maintaining project knowledge across development sessions.

## Memory Bank initialization and maintenance
- Memory Bank MUST be read completely at the start of every session - this is not optional
- Read Memory Bank files in hierarchical order: projectbrief.md → productContext.md → systemPatterns.md → techContext.md → activeContext.md → progress.md
- Memory Bank directory must contain all 6 core files before proceeding with development work
- When Memory Bank is empty or incomplete, initialization takes priority over all other tasks

## Documentation standards
- Documentation-first approach: complete comprehensive documentation before making code changes
- Hierarchical structure: build documentation in dependency order with clear relationships
- Future-proof format: use Markdown for accessibility and version control compatibility
- Comprehensive coverage: include both technical and business context in all documentation

## Active context management
- Update activeContext.md at the start of each session with current work focus
- Document recent activities, immediate next steps, and active decisions
- Capture project insights, learnings, and patterns discovered during development
- Record development environment status and key preferences

## Memory Bank update triggers
- After implementing significant changes to the codebase
- When discovering new project patterns or architectural insights
- When user explicitly requests with "update memory bank" (must review ALL files)
- When context needs clarification for future development sessions

## Progress tracking requirements
- Maintain clear status indicators: what works, what's partially implemented, what's missing
- Document known issues, technical debt, and external dependencies
- Track evolution of project decisions and architectural choices
- Establish clear priorities for next development iterations

## Project continuity standards
- All essential project knowledge must be documented in Memory Bank
- Technical context must be sufficient for development continuation
- Business context must be clear for feature prioritization
- Architecture must be documented for system modifications
- Memory Bank serves as the only link between development sessions
