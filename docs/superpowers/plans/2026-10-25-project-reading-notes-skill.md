# Project Reading Notes Skill Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a repository-scoped skill that automatically handles book and standalone-article interpretation artifacts, then commits and pushes only the relevant outputs.

**Architecture:** Create one self-contained project skill at `.agents/skills/managing-reading-notes/SKILL.md`. Its discovery description limits implicit activation to book and standalone-article interpretation, while its body defines classification, storage, Markdown naming, verification, scoped Git staging, commit, and push behavior.

**Tech Stack:** Agent Skills `SKILL.md`, Git, Markdown

**Spec:** `docs/superpowers/specs/2026-10-25-project-book-notes-skill-design.md`

## Global Constraints

- Activate only for book, chapter, reading-note, core-idea, or standalone-article interpretation tasks.
- Store standalone articles under the repository-root `article/` directory; keep book chapters under their book directory.
- Stage only files created or modified for the current interpretation task.
- Never force-push, rewrite history, delete user files, or include unrelated working-tree changes.
- Preserve local files and commits when push cannot complete, and report the exact failed stage.

## Review Focus

- An article mentioning a book must remain an article unless it has an explicit chapter relationship.
- An existing book directory must be reused rather than duplicated with punctuation or subtitle variations.
- A filename collision must not silently overwrite an unrelated note.
- Unrelated staged or unstaged changes must not enter the interpretation commit.
- Missing upstream, authentication failure, or remote rejection must stop safely without force-push or repeated mutation.

---

### Task 1: Create and validate the repository-scoped reading workflow

**Files:**
- Create: `.agents/skills/managing-reading-notes/SKILL.md`
- Modify: none
- Test: structural and content validation commands

**Interfaces:**
- Consumes: user requests for book, chapter, reading-note, core-idea, or standalone-article interpretation; `book-reader` for book-related analysis; the current Git repository and configured upstream.
- Produces: Markdown files in `<书名>/` or `article/`, plus a scoped commit pushed to the current branch upstream when available.

- [ ] **Step 1: Verify the skill does not exist yet**

Run: `test ! -e .agents/skills/managing-reading-notes/SKILL.md`

Expected: exit 0, proving the new path is absent before implementation.

- [ ] **Step 2: Create the minimal self-contained skill**

Create `.agents/skills/managing-reading-notes/SKILL.md` with:

- frontmatter name `managing-reading-notes`;
- a third-person `Use when...` description containing only the book/article interpretation trigger boundary;
- a classification rule for whole book, book chapter/topic, and standalone article;
- output rules for `<书名>/` and `article/` with one `.md` extension;
- collision handling that updates only an explicitly identified existing note and otherwise creates a distinct filename;
- verification of path, non-empty Markdown, and scoped diff;
- explicit-path staging, scoped commit, and ordinary upstream push;
- safe stopping behavior for unrelated changes, missing upstream, authentication failure, and rejected pushes.

- [ ] **Step 3: Run the official skill structure validator**

Run: `/Users/minyanhua/.codex/skills/.system/skill-creator/scripts/quick_validate.py .agents/skills/managing-reading-notes`

Expected: validation succeeds with no invalid frontmatter, naming, or scaffold placeholders.

- [ ] **Step 4: Verify the workflow contract**

Run targeted `rg` checks against the skill for `book-reader`, `article/`, `.md`, explicit-path staging, unrelated changes, ordinary push, push failure, and no force-push behavior.

Expected: every required contract is present, the description does not summarize the workflow, and the file stays below 500 words.

- [ ] **Step 5: Review the actual Git diff**

Run: `git diff --check && git diff -- .agents/skills/managing-reading-notes/SKILL.md docs/superpowers/specs/2026-10-25-project-book-notes-skill-design.md docs/superpowers/plans/2026-10-25-project-reading-notes-skill.md`

Expected: no whitespace errors; only the approved design, plan, and project skill are changed.

- [ ] **Step 6: Commit and push the project skill**

Stage only the design, plan, and skill paths. Commit with `feat: add project reading notes skill`, push `main` to `origin`, then verify local `HEAD` equals `origin/main` and the worktree is clean.
