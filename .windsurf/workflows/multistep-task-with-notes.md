---
description: A complex refactoring that requires note taking steps in between.
---

1. Check in notes/ and subdirectories if you have already taken notes useful for this task.
2. Check in docs/ and subdirectories if there is knowledge about workflows, the code base and design decisions that you need to consider for this task.
3. Plan the necessary steps for this task and either update existing notes or create new ones. Include a checklist with subtasks that you can regularly check and update (use `- [ ]` for checkboxes).
4. Start working on the next open subtask.
5. Update the notes with what you have done and need to know for later and update the checklist with the current progress.
6. Check the checklist for the next open subtask and repeat from step 4. If all subtasks are finished proceed to step 7.
7. Run tests and fix errors. 
8. Go through all changed files and notes and tidy up. Make everything nice for production. Remove unnecessary comments and log statements. Identify dead code resulting from the changes and remove it.
9. Go through all the changes and the notes and check if you have learned something that should be in the docs. If so, find an appropriate spot in the files in the docs directory and add them. Be very selective in this step. The docs contain general things not details about every model.
10. Commit your changes, push to remote, and open a PR for review.