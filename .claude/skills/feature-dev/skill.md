---
name: feature-dev
description: Comprehensive feature development workflow with specialized agents for codebase exploration, architecture design, and quality review. Use /feature-dev to start a guided 7-phase workflow for building new features.
---

# Feature Development Skill

A comprehensive, structured workflow for feature development with specialized agents for codebase exploration, architecture design, and quality review.

## Command: `/feature-dev`

Launches a guided feature development workflow with 7 distinct phases.

**Usage:**
```bash
/feature-dev Add user authentication with OAuth
```

Or simply:
```bash
/feature-dev
```

## The 7-Phase Workflow

### Phase 1: Discovery
- Clarifies the feature request
- Identifies constraints and requirements
- Confirms understanding with user

### Phase 2: Codebase Exploration
- Launches 2-3 `code-explorer` agents in parallel
- Each agent explores different aspects (similar features, architecture, patterns)
- Returns key files to read for deep understanding

### Phase 3: Clarifying Questions
- Identifies underspecified aspects: edge cases, error handling, integration points
- **Waits for answers before proceeding**

### Phase 4: Architecture Design
- Launches 2-3 `code-architect` agents with different focuses
- Presents comparison with trade-offs and recommendation
- **Asks which approach you prefer**

### Phase 5: Implementation
- **Waits for explicit approval** before starting
- Implements following chosen architecture
- Follows codebase conventions strictly

### Phase 6: Quality Review
- Launches 3 `code-reviewer` agents in parallel
- Presents findings and asks what to do (fix now, fix later, proceed)

### Phase 7: Summary
- Documents what was built
- Key decisions made
- Files modified
- Suggested next steps

## When to Use

**Use for:**
- New features that touch multiple files
- Features requiring architectural decisions
- Complex integrations with existing code
- Features where requirements are somewhat unclear

**Don't use for:**
- Single-line bug fixes
- Trivial changes
- Urgent hotfixes
