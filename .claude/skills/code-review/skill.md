---
name: code-review
description: Automated code review for pull requests using multiple specialized agents with confidence-based scoring to filter false positives. Use /code-review to review the current PR.
---

# Code Review Skill

Automated code review for pull requests using multiple specialized agents with confidence-based scoring to filter false positives.

## Command: `/code-review`

Performs automated code review on a pull request using multiple specialized agents.

**Usage:**
```bash
# Local review (outputs to terminal)
/code-review

# Post as PR comment
/code-review --comment
```

## What It Does

1. **Validation**: Skips closed, draft, trivial, or already-reviewed PRs
2. **Data gathering**: Collects CLAUDE.md guideline files from the repository
3. **Summarization**: Creates PR change summary
4. **Parallel review**: Launches 4 independent agents:
   - **Agents #1 & #2**: CLAUDE.md compliance audit
   - **Agent #3**: Bug detection in changes
   - **Agent #4**: Bug detection with context
5. **Validation**: Each issue is validated by a separate agent
6. **Filtering**: Removes low-confidence issues
7. **Output**: Posts inline comments on PR (with `--comment`) or outputs to terminal

## Confidence Scoring

- **0**: Not confident, false positive
- **25**: Somewhat confident, might be real
- **50**: Moderately confident, real but minor
- **75**: Highly confident, real and important
- **100**: Absolutely certain, definitely real

Only issues >= 80 confidence are reported.

## False Positives Filtered

- Pre-existing issues not in PR
- Code appearing like bugs but isn't
- Pedantic nitpicks
- Issues linters catch
- General quality issues (unless in CLAUDE.md)

## Requirements

- Git repository with GitHub integration
- GitHub CLI (`gh`) installed and authenticated
- CLAUDE.md files (optional but recommended)

## Best Practices

- Maintain clear CLAUDE.md files for better compliance checking
- Trust the 80+ confidence threshold
- Run on all non-trivial pull requests
- Use as starting point for human review
