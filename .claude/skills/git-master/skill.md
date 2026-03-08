---
name: git-master
description: Advanced Git operations skill for handling merge conflicts, rebasing, cherry-picking, bisecting, and complex branch management. Automatically activates when Git issues arise. Makes complicated Git operations simple and safe.
---

# Git Master Skill

Advanced Git operations made simple. Handles merge conflicts, rebasing, cherry-picking, bisecting, and complex branch management with safety-first approach.

## When This Skill Activates

- "I have a merge conflict"
- "Help me rebase"
- "Cherry-pick commits from..."
- "Find which commit broke..."
- "Undo my last commit"
- "Clean up my branch history"
- "Squash my commits"
- "I messed up my Git"

## Safety-First Principles

1. **Always create backup branch** before destructive operations
2. **Stash uncommitted changes** before operations
3. **Explain what will happen** before executing
4. **Provide rollback instructions** after operations

## Quick Reference Commands

### Before Any Risky Operation
```bash
# Create safety backup
git branch backup-$(date +%Y%m%d-%H%M%S)

# Stash any uncommitted work
git stash push -m "before-risky-operation"
```

---

## Core Workflows

### Workflow 1: Merge Conflict Resolution

**When:** `git merge` or `git pull` shows conflicts

**Process:**
1. Identify conflicted files: `git status`
2. For each conflict, choose strategy:
   - **Keep ours**: `git checkout --ours <file>`
   - **Keep theirs**: `git checkout --theirs <file>`
   - **Manual merge**: Edit file, remove conflict markers
3. Stage resolved files: `git add <file>`
4. Complete merge: `git commit`

**Conflict Markers Explained:**
```
<<<<<<< HEAD
Your changes (current branch)
=======
Their changes (incoming branch)
>>>>>>> feature-branch
```

**Pro Tips:**
```bash
# See what changed on both sides
git diff --ours <file>    # Your changes
git diff --theirs <file>  # Their changes

# Use merge tool
git mergetool

# Abort if overwhelmed
git merge --abort
```

---

### Workflow 2: Interactive Rebase (Clean History)

**When:** Need to squash, reorder, edit, or drop commits

**Process:**
```bash
# Rebase last N commits
git rebase -i HEAD~N

# Rebase onto main
git rebase -i main
```

**Interactive Commands:**
| Command | Effect |
|---------|--------|
| `pick` | Keep commit as-is |
| `reword` | Keep commit, edit message |
| `edit` | Pause to amend commit |
| `squash` | Combine with previous commit |
| `fixup` | Combine, discard this message |
| `drop` | Delete commit |

**Example: Squash Last 3 Commits:**
```bash
git rebase -i HEAD~3

# In editor, change:
pick abc123 First commit
squash def456 Second commit
squash ghi789 Third commit

# Save, then edit combined message
```

**If Rebase Goes Wrong:**
```bash
git rebase --abort  # Cancel and restore
```

---

### Workflow 3: Cherry-Pick Commits

**When:** Need specific commits from another branch

**Single Commit:**
```bash
git cherry-pick <commit-sha>
```

**Multiple Commits:**
```bash
git cherry-pick <sha1> <sha2> <sha3>
```

**Range of Commits:**
```bash
# From A (exclusive) to B (inclusive)
git cherry-pick A..B

# From A (inclusive) to B (inclusive)
git cherry-pick A^..B
```

**With Conflicts:**
```bash
# Resolve conflicts, then:
git cherry-pick --continue

# Or abort:
git cherry-pick --abort
```

**Cherry-Pick Without Committing:**
```bash
git cherry-pick -n <sha>  # Stage changes only
```

---

### Workflow 4: Git Bisect (Find Bug Source)

**When:** Need to find which commit introduced a bug

**Process:**
```bash
# Start bisect
git bisect start

# Mark current (broken) as bad
git bisect bad

# Mark known good commit
git bisect good <known-good-sha>

# Git checks out middle commit
# Test it, then:
git bisect good  # If working
git bisect bad   # If broken

# Repeat until found
# Git will report: "<sha> is the first bad commit"

# End bisect
git bisect reset
```

**Automated Bisect:**
```bash
# Run test script automatically
git bisect start HEAD <good-sha>
git bisect run ./test-script.sh
```

---

### Workflow 5: Undo Operations

**Undo Last Commit (Keep Changes):**
```bash
git reset --soft HEAD~1
```

**Undo Last Commit (Discard Changes):**
```bash
git reset --hard HEAD~1
```

**Undo Pushed Commit (Safe):**
```bash
git revert <sha>  # Creates new commit that undoes changes
```

**Recover Deleted Branch:**
```bash
git reflog  # Find the SHA
git checkout -b recovered-branch <sha>
```

**Unstage Files:**
```bash
git reset HEAD <file>
# Or (modern):
git restore --staged <file>
```

**Discard Local Changes:**
```bash
git checkout -- <file>
# Or (modern):
git restore <file>
```

---

### Workflow 6: Branch Cleanup

**Delete Local Branch:**
```bash
git branch -d branch-name    # Safe (checks if merged)
git branch -D branch-name    # Force delete
```

**Delete Remote Branch:**
```bash
git push origin --delete branch-name
```

**Prune Stale Remote Branches:**
```bash
git fetch --prune
git remote prune origin
```

**Clean Up Merged Branches:**
```bash
# List merged branches
git branch --merged main

# Delete all merged (except main/master)
git branch --merged main | grep -v "main\|master" | xargs git branch -d
```

---

### Workflow 7: Stash Management

**Stash Changes:**
```bash
git stash push -m "description"
```

**List Stashes:**
```bash
git stash list
```

**Apply Stash:**
```bash
git stash pop           # Apply and remove
git stash apply         # Apply and keep
git stash apply stash@{2}  # Apply specific
```

**View Stash Contents:**
```bash
git stash show -p stash@{0}
```

**Drop Stash:**
```bash
git stash drop stash@{0}
git stash clear  # Drop all
```

---

### Workflow 8: Advanced History

**View Commit Graph:**
```bash
git log --oneline --graph --all
```

**Find Commits by Message:**
```bash
git log --grep="keyword"
```

**Find Commits Changing File:**
```bash
git log --follow -p -- path/to/file
```

**Find Who Changed Line:**
```bash
git blame path/to/file
git blame -L 10,20 path/to/file  # Lines 10-20
```

**Search Code History:**
```bash
git log -S "function_name" --source --all
```

---

## Emergency Recovery

### "I Messed Up Everything"

```bash
# Step 1: Don't panic. Check reflog
git reflog

# Step 2: Find the SHA before the mess
# Step 3: Reset to that point
git reset --hard <safe-sha>
```

### "I Committed to Wrong Branch"

```bash
# Step 1: Note the commit SHA
git log -1  # Copy SHA

# Step 2: Remove from current branch
git reset --hard HEAD~1

# Step 3: Apply to correct branch
git checkout correct-branch
git cherry-pick <sha>
```

### "I Need My Deleted File Back"

```bash
# Find when file was deleted
git log --diff-filter=D --summary | grep <filename>

# Restore from commit before deletion
git checkout <sha>^ -- path/to/file
```

---

## GitHub CLI Integration

**Create Issue:**
```bash
gh issue create --title "Bug: X" --body "Description"
```

**View PR:**
```bash
gh pr view <number>
gh pr diff <number>
```

**Checkout PR:**
```bash
gh pr checkout <number>
```

**Create PR:**
```bash
gh pr create --title "Feature" --body "Description"
```

**Merge PR:**
```bash
gh pr merge <number> --squash --delete-branch
```

**View CI Status:**
```bash
gh pr checks <number>
gh run list
gh run view <run-id>
```
