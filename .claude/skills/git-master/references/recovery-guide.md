# Git Recovery Guide

## The Golden Rule

**Git almost never truly deletes data.** If you committed it, it's recoverable via reflog for at least 30 days.

```bash
# Your safety net
git reflog
```

---

## Common Disasters & Recovery

### 1. "I deleted commits I need"

```bash
# Find lost commits
git reflog

# Example output:
# abc1234 HEAD@{0}: reset: moving to HEAD~3
# def5678 HEAD@{1}: commit: Important feature  <-- Lost commit!
# ...

# Recover
git checkout -b recovery-branch def5678
# Or reset current branch
git reset --hard def5678
```

### 2. "I force pushed and lost remote commits"

```bash
# If you have local copy
git push --force origin branch-name

# If someone else has the commits
# Ask them to push, or:
git fetch origin
git reset --hard origin/branch-name@{1}  # Previous state
```

### 3. "I accidentally deleted a branch"

```bash
# Find the branch tip
git reflog | grep "branch-name"
# Or
git reflog --all | grep "checkout"

# Recreate
git checkout -b branch-name <sha>
```

### 4. "I committed to the wrong branch"

```bash
# Option A: Move commits to correct branch
git checkout correct-branch
git cherry-pick <sha>
git checkout wrong-branch
git reset --hard HEAD~1

# Option B: Create new branch from commits
git branch new-feature  # Creates branch at current HEAD
git reset --hard HEAD~1  # Remove from wrong branch
```

### 5. "My merge went horribly wrong"

```bash
# If not yet committed
git merge --abort

# If already committed
git reset --hard ORIG_HEAD

# If pushed (safe revert)
git revert -m 1 <merge-commit-sha>
```

### 6. "I need a deleted file back"

```bash
# Find when it was deleted
git log --diff-filter=D --summary --all -- "**/filename*"

# Restore from commit before deletion
git show <sha-before-delete>:path/to/file > path/to/file
# Or
git checkout <sha-before-delete>^ -- path/to/file
```

### 7. "I overwrote my local changes"

```bash
# If you staged (git add) before
git fsck --lost-found
# Check .git/lost-found/other/

# If never staged, check IDE local history
# VS Code: File > Local History
```

### 8. "Rebase went wrong, conflicts everywhere"

```bash
# Abort and start fresh
git rebase --abort

# Your branch is back to pre-rebase state
```

### 9. "I amended the wrong commit"

```bash
# Find original commit
git reflog

# Reset to pre-amend state
git reset --soft HEAD@{1}

# Now you have both versions available
```

### 10. "I need to undo a revert"

```bash
# Revert the revert (yes, really)
git revert <revert-commit-sha>
```

---

## Reflog Deep Dive

### Understanding Reflog

Reflog tracks where HEAD has pointed. Every checkout, commit, reset, rebase is logged.

```bash
# View reflog
git reflog

# With timestamps
git reflog --date=relative

# For specific branch
git reflog show branch-name
```

### Reflog Syntax

```bash
HEAD@{0}     # Current HEAD
HEAD@{1}     # Previous HEAD position
HEAD@{5}     # 5 moves ago
HEAD@{yesterday}  # Yesterday
HEAD@{2.days.ago} # 2 days ago
main@{1}     # main branch 1 move ago
```

### Using Reflog to Compare

```bash
# See what changed
git diff HEAD@{0} HEAD@{5}

# See log between states
git log HEAD@{5}..HEAD@{0}
```

---

## Preventive Measures

### 1. Regular Backups

```bash
# Before risky operations
git branch backup-$(date +%Y%m%d-%H%M%S)
```

### 2. Push Frequently

```bash
# Remote is your backup
git push origin branch-name
```

### 3. Use --dry-run

```bash
git clean -fd --dry-run  # See what would be deleted
git push --dry-run       # See what would be pushed
```

### 4. Set Up Aliases for Safety

```bash
# In ~/.gitconfig
[alias]
    backup = "!git branch backup-$(date +%Y%m%d-%H%M%S)"
    undo = "reset --soft HEAD~1"
    uncommit = "reset --soft HEAD~1"
```

---

## When All Else Fails

### Git FSck (File System Check)

```bash
# Find dangling objects
git fsck --full --no-reflogs

# Recover dangling commits
git show <dangling-commit-sha>
```

### Check .git Directory

```bash
# Stashed changes
ls .git/refs/stash

# Lost objects
ls .git/lost-found/

# Recent operations
cat .git/logs/HEAD
```

### Professional Help

If data is critical and above methods fail:
1. **Don't run more git commands** (might overwrite)
2. Copy entire `.git` directory as backup
3. Consider git recovery tools or services
