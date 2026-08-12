# Multi-Path Installation Guide Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add one authoritative installation guide with several practical installation paths, including optional Codex assistance.

**Architecture:** Keep installation policy in root `INSTALL.md`, link to it from user-facing READMEs, and include it in source release archives. Protect the archive contract with the existing packaging regression test.

**Tech Stack:** Markdown, Bash release packaging, Python unittest.

---

### Task 1: Add the installation guide

**Files:**
- Create: `INSTALL.md`
- Modify: `README.md`
- Modify: `docs/desktop-user-guide.md`
- Modify: `macos-native/README.md`

- [x] Document Codex-assisted, manual, source, upgrade, and clean-host paths.
- [x] Clearly distinguish notarized distribution packages from development prereleases.
- [x] Add safety boundaries and concrete post-install verification steps.

### Task 2: Ship the guide in source releases

**Files:**
- Modify: `release/package.sh`
- Modify: `tests/test_native_app_packaging.py`

- [x] Add a failing assertion that `INSTALL.md` exists in the source archive.
- [x] Add `INSTALL.md` to the explicit tar input list.
- [x] Run `python3 -m unittest -v tests.test_native_app_packaging.NativeAppPackagingTests.test_development_release_creates_explicitly_labeled_app_zip` and expect `OK`.

### Task 3: Validate documentation

**Files:**
- Verify: `INSTALL.md`
- Verify: `README.md`
- Verify: `docs/desktop-user-guide.md`
- Verify: `macos-native/README.md`

- [x] Check local Markdown links resolve to existing files.
- [x] Search the installation guide for forbidden destructive commands.
- [x] Run `git diff --check` and review the final diff.
