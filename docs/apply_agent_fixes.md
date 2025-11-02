# Loading Agent Fixes into Your Project

This guide explains a few ways to pull the latest fixes produced by the AI agent into your local clone of the project. Choose the approach that best fits how you collaborate with the agent.

## 1. Pull from the agent's branch (recommended)

1. Add the agent's repository as a remote if you have not already:
   ```bash
   git remote add agent <AGENT_REPO_URL>
   ```
   Replace `<AGENT_REPO_URL>` with the HTTPS URL of the agent-maintained fork.

2. Fetch the latest changes:
   ```bash
   git fetch agent
   ```

3. Merge or rebase the target branch (for example, `agent/main`) onto your working branch:
   ```bash
   git checkout <your-working-branch>
   git merge agent/main
   # or, if you prefer a rebase
   git rebase agent/main
   ```

## 2. Cherry-pick a specific commit

If you only need the most recent commit produced by the agent, you can cherry-pick it directly:

1. Find the commit hash from the agent's summary (for example, `abc1234`).
2. Fetch the commit from the agent remote:
   ```bash
   git fetch agent abc1234
   ```
3. Apply it to your branch:
   ```bash
   git cherry-pick abc1234
   ```

## 3. Apply the patch file manually

When you cannot add a remote, ask the agent for the raw patch (generated via `git format-patch`). Then apply it locally:

```bash
git apply < path/to/patch.diff
```

Resolve any conflicts, run tests, and commit the merge results as usual.

## 4. Validate and push

After integrating the fixes, make sure to:

1. Install any new dependencies:
   ```bash
   pip install -r requirements.txt
   ```
2. Run the project test suite or key smoke tests.
3. Push the updated branch to your origin remote and open a pull request for review.

---

Keeping a clean history (for example, using rebase before opening your PR) helps reviewers track the agent's contributions alongside your own work.

## Appendix: Refreshing the changes in PyCharm

If you prefer to stay inside PyCharm for Git operations, follow this flow after the agent notifies you about a new commit:

1. Open the **Git** tool window (usually at the bottom) and make sure the project is on the branch where you want the update.
2. Press <kbd>Ctrl</kbd> + <kbd>T</kbd> (or choose **VCS ▸ Git ▸ Fetch**) to download the latest refs from the `agent` remote. PyCharm will show the incoming commits in the notification pop-up.
3. When the fetch completes, click **Update Project…** in the pop-up (or use <kbd>Ctrl</kbd> + <kbd>Alt</kbd> + <kbd>Y</kbd>) and select **Merge** or **Rebase** depending on your preference. This pulls the agent's commits into your branch.
4. If you only need a single commit, locate it in the **Log** tab, right-click it, and choose **Cherry-Pick**.
5. After the update, PyCharm may prompt you to reload changed files. Accept the prompt so the editor reflects the new state.
6. Finally, run your usual tests (for example via Run Configurations) before continuing your work.

These steps mirror the command-line instructions above but keep the entire workflow inside the IDE.

### Частые вопросы

- **Нужно ли нажимать кнопку «Обновить ветку» на GitHub перед работой в PyCharm?** Нет, достаточно выполнить описанный выше Fetch и Update Project внутри PyCharm. Кнопка на GitHub лишь синхронизирует ветку в удалённом репозитории, но не влияет на локальную копию в IDE.
- **Почему в данных всё ещё появляется путь к XML-отчёту?** Pytest продолжает генерировать JUnit XML, чтобы мы могли собрать статистику по тестам. Этот файл используется только внутри сервера и больше не отдаётся через REST-эндпоинты.
