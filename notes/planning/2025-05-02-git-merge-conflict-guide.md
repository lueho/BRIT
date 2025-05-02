# Step-by-Step Guide: Resolving Git Merge Conflicts

This guide walks you through resolving merge conflicts in Git, as encountered during `git merge projects-module`.

---

## 1. Identify the Conflicted Files
After running `git merge <branch>`, Git will report files with conflicts. In your case:
- `.gitignore`
- `docker-compose.yml`

---

## 2. View the Conflict Markers
Open each conflicted file. You will see sections like:

```text
<<<<<<< HEAD
# your branch's content
=======
# merging branch's content
>>>>>>> projects-module
```

---

## 3. Edit the Files to Resolve Conflicts
- Decide which changes to keep: yours, theirs, or a combination.
- Remove all conflict markers (`<<<<<<<`, `=======`, `>>>>>>>`).
- Save the file.

---

## 4. Mark Files as Resolved
After editing, mark each file as resolved:
```sh
git add .gitignore
git add docker-compose.yml
```

---

## 5. Finalize the Merge
Commit the resolved merge:
```sh
git commit
```
- Git will open your editor with a default merge commit message. Optionally edit it, then save and close.

---

## 6. Verify the Merge
- Run `git status` to confirm there are no staged or unstaged changes left.
- Test your application to ensure everything works as expected.

---

## 7. Clean Up (Optional)
- Delete the merged branch if no longer needed: `git branch -d projects-module`

---

## Troubleshooting
- If you want to abort the merge: `git merge --abort`
- If you need to see a visual diff: use your IDE or `git diff`.

---

**References:**
- [Git Docs: Resolving a merge conflict](https://git-scm.com/docs/git-merge#_how_to_resolve_conflicts)
- [Atlassian: Resolve merge conflicts](https://www.atlassian.com/git/tutorials/using-branches/merge-conflicts)

---

*Last updated: 2025-05-02*
