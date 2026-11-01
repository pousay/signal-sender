---
name: github-contribution
description: Use when delivering a code change through GitHub with standard issues, conventional commits, feature branches, pull requests, and a mandatory user code-review gate before every merge. Covers planning, commit/branch/PR sizing, review feedback, sequential merges, and branch cleanup.
compatibility: opencode
---

# GitHub Contribution Workflow

Deliver work as a sequence of small, reviewable GitHub contributions. Every
branch maps to one issue and one pull request. Merge only after the user has
reviewed and approved. Then clean up and continue to the next branch.

This skill is the default for "make a PR", "fix this on a branch", "open an
issue", or any multi-step code change that should land on GitHub.

## Non-negotiable rules

1. **Never merge a PR, and never merge one working branch into another,
   without explicit user approval after code review.** Approval means either
   an `APPROVED` GitHub review or an explicit message from the user such as
   "approved" or "merge it". Silence, a comment, or passing CI is not
   approval.
2. Never commit or push directly to the default branch (`master`/`main`).
3. Never force-push a default branch. Avoid force-pushing a reviewed feature
   branch; if it is unavoidable (conflict resolution), explain why, use
   `--force-with-lease`, and request a fresh review.
4. Never delete a branch, local or remote, before its PR is merged.
5. One issue per PR. One branch per PR. Do not create an issue per commit.
6. Do not pad the history. A commit must represent a real, coherent step;
   never split by file or invent commits to look busy.
7. Do not mix unrelated fixes, refactors, or formatting into a PR. Open a
   separate issue/PR if it is worth doing.
8. Follow repository policy. If the repo forbids tests or comments, do not add
   them. Run whatever checks the repo does define.
9. Never commit secrets or runtime state (`.env`, `accounts.json`, session
   files, logs, tokens, generated backups). Inspect `git diff --cached` before
   every commit.
10. If `gh` is unavailable or unauthenticated, stop and report it. Never fake
    issue/PR links or claim a push succeeded.

## Phase 0 — Preflight

```bash
git status --short
gh auth status
gh repo view --json nameWithOwner,defaultBranchRef
```

- Require a clean worktree, or explicitly account for existing user changes.
  Never discard someone else's work.
- Read `AGENTS.md`, `README.md`, and any project rules before planning.
- Let `base` be the repository's actual default branch, not an assumed
  `master`.
- Sync before starting and before every new branch:

```bash
git fetch origin
git switch <base>
git pull --ff-only
```

- **Resume first:** if an epic issue, open PR, or existing branch already
  covers this task, continue it instead of creating duplicates. Check:

```bash
gh issue list --state open
gh pr list --state open
git branch -vv
gh pr status
```

## Phase 1 — Plan the contribution set

Split the task into the smallest number of independently reviewable outcomes.
A reviewer should be able to understand and judge one PR without reading the
next one.

Standard sizing:

| Task size | Issues | Branches / PRs | Commits per branch |
| --------- | ------ | -------------- | ------------------ |
| Small     | 1      | 1              | 1–3                |
| Medium    | 2–3    | 2–3            | 2–4                |
| Large     | 4–6    | 4–6            | 2–5                |

- More than six open review units means the task should be split into phases
  with the user first.
- A PR should normally stay under ~400 changed lines and ~10 files. Split by
  behavior, not by file count.
- Order branches by dependency: branch N+1 starts from the default branch
  **after** branch N is merged. Do not stack or merge working branches to make
  progress.
- For multi-branch work, create one epic/tracking issue containing a task-list
  of the sub-issues. Close the epic only after all sub-issues are closed.
- Each sub-issue is delivered by exactly one PR. Reference the epic from the
  sub-issue (`Parent: #<epic>`), and the sub-issues from the epic checklist.
- If scope is ambiguous or the plan needs more than six branches, ask the user
  before creating anything public.

Notify the user that substantial work is starting:

```bash
tg-notify start "<task> — planning <N> issues/PRs"
```

Use `tg-notify msg` for the plan only when it adds value; do not spam.

### Issue template

Create with a heredoc to preserve formatting:

```bash
gh issue create --title "fix(seeder): prevent duplicate creation on partial failure" --body-file - <<'EOF'
## Context
What is happening today and why it matters.

## Goal
The concrete outcome this issue delivers.

## Scope
- In scope: ...
- Out of scope: ...

## Acceptance criteria
- [ ] ...
- [ ] ...

## Verification
Commands or manual checks that prove the criteria.

## Related
Parent: #<epic>   # omit for single-issue tasks
EOF
```

Issue titles use the same `type(scope): imperative summary` style as commits.
Use existing labels (`bug`, `enhancement`, `documentation`, ...); do not create
a label taxonomy for a small task.

## Phase 2 — Delivery loop (repeat per branch)

### 1. Branch from the updated base

```bash
git fetch origin
git switch <base>
git pull --ff-only
git switch -c <type>/<issue-number>-<kebab-slug> origin/<base>
```

Examples: `fix/42-seeder-partial-failure`, `feat/57-account-lock`,
`docs/63-readme-review`. Lowercase ASCII, kebab-case, about 50 characters max.
Never use `dev`, `test`, `update`, or a bare username as a branch name.

### 2. Implement and verify

- Make the smallest coherent change that satisfies the issue.
- Run the repository's checks (syntax, lint, build, tests if allowed).
  For this Python repo, at minimum:

```bash
python3 -m compileall -q main.py bot core logger
git diff --check
```

- Review the staged diff for secrets and unrelated files before committing.

### 3. Commit in conventional style

One logical step per commit, each leaving the branch usable.

```
type(scope): imperative summary

Explain why the change is needed and what it affects. Wrap the body
at 72 characters. Do not narrate individual lines.

Refs: #<issue>
```

Rules:

- Types: `feat`, `fix`, `refactor`, `perf`, `docs`, `style`, `test`, `build`,
  `ci`, `chore`, `revert`.
- Scope: the module or area (`seeder`, `storage`, `cron`, `handlers`, `config`,
  `logging`). Omit only for repo-wide changes.
- Subject: lowercase after the colon, imperative mood, no trailing period,
  72 characters max.
- Breaking changes: use `type(scope)!:` and add a
  `BREAKING CHANGE: <impact>` footer.
- Use `Refs: #<issue>` in every commit. Do **not** put `Closes` in intermediate
  commits; the PR owns closure.
- Do not use `WIP`, `fixup!`, `tmp`, or checkpoint commits in a pushed branch.
  Squash locally before the first push if you used them.
- After review feedback, add a normal `fix(scope): address review ...` commit.
  Do not amend or force-push reviewed history unless the user asks.

Verify the branch history before pushing:

```bash
git log --oneline origin/<base>..HEAD
git status --short
```

### 4. Push and open the PR

```bash
git push -u origin <branch>

gh pr create --base <base> --head <branch> \
  --title "type(scope): imperative summary" \
  --body-file - <<'EOF'
## Summary
What this PR delivers and why. One short paragraph.

Closes #<issue>

## Task context
Explain the problem and the desired behavior in enough detail that a reviewer
who has not read the issue can follow it.

## Changes
- `path/to/file.py`: what changed and why.
- `path/to/other.py`: what changed and why.

## Approach
Why this design was chosen. Mention alternatives only when the trade-off is
non-obvious.

## Verification
Commands run and their results. Include manual checks for Telegram flows
(buttons, callbacks, permissions, cron timing).

## Risk and rollback
What could break, how it is contained, and how to revert this PR.

## Review guide
Suggested review order and the specific decisions that deserve scrutiny.

## Checklist
- [ ] Conventional PR title
- [ ] Linked issue
- [ ] Checks pass
- [ ] No secrets or generated files
- [ ] Docs updated if behavior changed
EOF
```

- PR title is a valid conventional commit subject.
- The body must explain both the task and the code. Never open a PR with only
  "fixes #N".
- `Closes #<issue>` in the PR body is what closes the issue on merge.
- If the repository allows review requests and the user's handle is known,
  request their review. Otherwise announce via `tg-notify`.
- Use a draft PR only while work is genuinely incomplete. A branch that is
  ready for review gets a ready PR.

### 5. Announce and stop for review

```bash
gh pr view <number> --json url,isDraft,reviewDecision,mergeable,statusCheckRollup
tg-notify msg "PR #<number> ready for review: <title>\n<url>\nIssue: #<issue>"
```

Then end the turn and wait. This is the mandatory review gate. Do not merge,
do not start the next branch, and do not mark anything complete.

### 6. Handle review feedback

- **Changes requested / comments:** address every point with new commits,
  reply to the relevant threads, push, and re-request review. Then wait again.
- **Checks failed:** fix them with a conventional commit, push, and wait for
  the checks to pass. If the fix is substantive, request a fresh review.
- **Approved:** continue to step 7 only when the approval is explicit.
- **Conflicts or base moved:** rebase onto the updated base only if needed.
  Prefer `gh pr update-branch` when the repo allows it; otherwise rebase,
  use `--force-with-lease`, and re-request review because approval may be
  dismissed.
- **User asks for scope changes:** update the issue scope first, then the PR.

### 7. Merge only after approval

Before merging, confirm all of these:

```bash
gh pr view <number> --json state,isDraft,reviewDecision,mergeable,statusCheckRollup
gh issue view <issue> --json state,title
```

- PR is open, not a draft, `reviewDecision` is `APPROVED` (or the user has
  explicitly approved in chat).
- `mergeable` is `MERGEABLE` and required checks pass.
- The branch is based on the current default branch.
- The working tree is clean and no unrelated changes are present.

Merge with the repository's allowed strategy. Default to rebase merge so the
conventional commits survive and history stays linear:

```bash
gh pr merge <number> --rebase --delete-branch
```

- If the repo only permits squash merges, squash and use the conventional PR
  title as the squash commit subject.
- Never use `--admin`, never bypass branch protection, and never enable
  auto-merge without the user asking.
- If the merge fails, stop and report the exact blocker; do not invent an
  alternative merge path.

After the merge:

```bash
git switch <base>
git pull --ff-only
git branch -d <branch>                    # if it still exists locally
git push origin --delete <branch>         # only if it still exists remotely
gh issue view <issue> --json state        # expect CLOSED
```

If `Closes` did not fire, close the issue manually with a comment linking the
merged PR. Comment on the PR with the merge commit and a one-line result when
that helps future readers. Tick the epic checklist item. Notify:

```bash
tg-notify msg "Merged PR #<number> (<merge-sha>). Issue #<issue> closed. Starting <next>."
```

Then repeat Phase 2 for the next branch from the updated base.

## Phase 3 — Finish

Only after every planned issue is closed and every PR is merged:

- Confirm no open PRs or branches remain for the task (except the base branch).
- Confirm the epic issue is closed with a short delivery summary.
- Confirm the default branch contains all merged commits:

```bash
git switch <base>
git pull --ff-only
git log --oneline -n 20
git branch -a
gh pr list --state open
```

Announce completion:

```bash
tg-notify finish "<task>: <N> issues closed, <N> PRs merged, branches deleted"
```

If blocked, send `tg-notify fail "<reason>"` and stop with the exact blocker.

## Resume protocol

State lives in GitHub, not in local notes:

- Epic issue checklist = remaining sub-issues.
- Open PR = work awaiting review or changes.
- Issue state = delivered or not.
- Branch list = local cleanup status.

On resume, read those four sources first (`gh issue list`, `gh pr list`,
`git branch -vv`, epic body), determine the current branch/PR, and continue at
the correct step. Never recreate an issue or branch that already exists.

## Review-gate summary

```
plan issues
  -> branch -> commits -> push -> PR -> announce
  -> WAIT for user review
  -> changes? new commits -> re-review -> WAIT
  -> approved? -> merge -> delete branch -> close issue
  -> next branch from updated base
  -> ...
  -> all merged -> close epic -> finish
```

No merge without review. No next branch until the current PR is merged. No
exception for "small" changes.
