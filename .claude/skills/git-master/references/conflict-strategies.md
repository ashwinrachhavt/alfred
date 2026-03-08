# Merge Conflict Resolution Strategies

## Understanding Conflict Types

### 1. Content Conflicts
Both branches modified the same lines differently.

```
<<<<<<< HEAD
const timeout = 5000;
=======
const timeout = 10000;
>>>>>>> feature
```

**Resolution:** Choose one value or combine logic.

### 2. Rename/Delete Conflicts
One branch renamed a file, another deleted it.

```bash
# See conflict details
git status

# Keep renamed version
git add <new-name>
git rm <old-name>

# Or keep deleted
git rm <new-name>
```

### 3. Binary Conflicts
Both branches modified a binary file (image, etc.).

```bash
# Keep ours
git checkout --ours path/to/file.png
git add path/to/file.png

# Keep theirs
git checkout --theirs path/to/file.png
git add path/to/file.png
```

---

## Resolution Strategies

### Strategy 1: Keep Ours (Current Branch Wins)

```bash
# Single file
git checkout --ours path/to/file

# All conflicts
git checkout --ours .
```

**Use when:** Your branch has the correct/newer implementation.

### Strategy 2: Keep Theirs (Incoming Branch Wins)

```bash
# Single file
git checkout --theirs path/to/file

# All conflicts
git checkout --theirs .
```

**Use when:** The incoming branch has better changes.

### Strategy 3: Manual Resolution

1. Open file in editor
2. Find conflict markers (`<<<<<<<`, `=======`, `>>>>>>>`)
3. Edit to combine or choose
4. Remove all conflict markers
5. Save and stage

**Use when:** Both changes are partially needed.

### Strategy 4: Use Merge Tool

```bash
git mergetool
```

Opens configured visual tool (VS Code, vim, etc.).

**Configure merge tool:**
```bash
git config --global merge.tool vscode
git config --global mergetool.vscode.cmd 'code --wait $MERGED'
```

---

## Preventing Conflicts

### 1. Rebase Before Merge
```bash
# On feature branch
git fetch origin
git rebase origin/main

# Then create PR
```

### 2. Smaller, Focused PRs
- One feature per PR
- Merge frequently
- Don't let branches diverge too long

### 3. Communication
- Coordinate on shared files
- Use code owners for critical paths
- Review PRs promptly

---

## Complex Conflict Scenarios

### Conflict During Rebase

```bash
# Resolve conflict
git add <resolved-file>

# Continue rebase
git rebase --continue

# Or abort entire rebase
git rebase --abort
```

### Conflict During Cherry-Pick

```bash
# Resolve conflict
git add <resolved-file>

# Continue cherry-pick
git cherry-pick --continue

# Or abort
git cherry-pick --abort
```

### Conflict with Submodules

```bash
# Update submodule to correct commit
cd submodule-path
git checkout <correct-sha>
cd ..
git add submodule-path
```

---

## Conflict Resolution Checklist

- [ ] Read both versions carefully
- [ ] Understand the intent of each change
- [ ] Check if tests exist for the changed code
- [ ] Remove ALL conflict markers
- [ ] Test after resolution
- [ ] Commit with clear message explaining resolution
