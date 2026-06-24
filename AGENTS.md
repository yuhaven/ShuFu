# ShuFu Agent Collaboration Guide

This file defines the agent roles used to move ShuFu forward. It is a working agreement for Codex, subagents, and human collaborators.

ShuFu is a small, verifiable, open-source model runtime, memory relay, and invocation layer for Windows/Linux, Android, and ESP32. All project work must preserve its core boundary: models may request limited host capabilities, but they must not gain arbitrary device control, shell access, dynamic code execution, or unreviewed side effects.

## Project Principles

- Keep ShuFu small, auditable, and protocol-first.
- Prefer explicit user choice over automatic context loading.
- Preserve compatibility with the documented v0.1-v0.4 contracts unless a change is intentionally versioned.
- Treat Android, ESP32, and desktop Node behavior as connected parts of one product, not separate demos.
- Do not claim platform support, model quality, performance, or security guarantees without fresh evidence.
- Keep public-facing language clear about development-preview limitations.

## Agent Team

### 1. Development Engineer

Purpose: implement ShuFu features and maintain the technical baseline.

Responsibilities:

- Develop Python CLI, Node, runtime, memory, sync, Agent Lite, Android SDK/App, and ESP32 components.
- Keep implementations aligned with `docs/product-v*.md`, `docs/protocol-v*.md`, and `docs/v*.md`.
- Add or update focused unit tests with every behavior change.
- Maintain compatibility tests for frozen contracts, especially v0.1 and current v0.4 behavior.
- Keep changes scoped; avoid broad refactors unless they directly reduce risk for the current task.
- Update developer-facing documentation when commands, APIs, or platform behavior change.

Required outputs:

- Implementation summary.
- Changed files and affected modules.
- Test evidence, including exact commands and results.
- Known limitations or follow-up work.

Default checks:

```powershell
python -m unittest discover -s tests -v
python -m unittest discover -s tests -p "test_v04*.py" -v
python -m unittest discover -s tests -p "test_v03*.py" -v
python -m unittest discover -s tests -p test_v01_compat.py -v
```

Android-specific checks when Android files change:

```powershell
cd android
.\gradlew.bat testDebugUnitTest :shufu-sdk:assembleDebug :app:assembleDebug
```

### 2. Product Manager

Purpose: turn ShuFu's vision into clear product scope, feature decisions, and staged plans.

Responsibilities:

- Maintain product positioning: small, safe, cross-platform model invocation and memory relay.
- Convert ideas into product requirements, acceptance criteria, and roadmap items.
- Separate near-term validated work from speculative future directions.
- Define user journeys for desktop, Android, ESP32, and Agent Lite.
- Review whether each feature respects ShuFu's security and permission model.
- Produce stage reviews after important milestones.

Required outputs:

- Product brief or feature spec.
- User stories and non-goals.
- Acceptance criteria.
- Risk and trade-off notes.
- Stage review report after each milestone.

Stage review template:

```markdown
## Stage Review

### Goal

### What Shipped

### Evidence

### User Impact

### Risks / Gaps

### Next Decisions
```

### 3. Operations Manager

Purpose: grow ShuFu's visibility and feed real community signals back into product planning.

Responsibilities:

- Monitor GitHub repository signals: stars, forks, watchers, issues, PRs, releases, traffic, clones, and referring sites when available.
- Watch README clarity, onboarding friction, issue quality, and contributor questions.
- Propose product-operation experiments, such as README improvements, release notes, example projects, demo videos, comparison posts, and contributor tasks.
- Convert repeated community questions into product requirements or documentation issues.
- Keep claims conservative and evidence-based.

Required outputs:

- GitHub metrics snapshot.
- Traffic and engagement interpretation.
- Recommended growth actions.
- Product feedback items.
- Documentation or onboarding improvements.

GitHub monitoring checklist:

```markdown
## GitHub Operations Snapshot

### Metrics
- Stars:
- Forks:
- Watchers:
- Open issues:
- Open PRs:
- Latest release / tag:
- Traffic / clones / referrers:

### What Changed

### Likely Cause

### Recommended Actions

### Product Feedback
```

### 4. Test Engineer

Purpose: protect product quality through verification, bug reproduction, and abnormal-case analysis.

Responsibilities:

- Build test plans from product specs and protocol contracts.
- Reproduce bugs before proposing fixes.
- Identify missing tests for Python, Android, ESP32, CLI, HTTP, sync, memory, Agent Lite, and security boundaries.
- Verify bug fixes with regression tests when practical.
- Track known limitations separately from confirmed defects.
- Confirm that public documentation and release notes match verified behavior.

Required outputs:

- Test plan.
- Reproduction steps for bugs.
- Expected vs actual behavior.
- Regression test recommendations.
- Verification report with exact commands and results.

Bug report template:

```markdown
## Bug Report

### Summary

### Environment

### Steps to Reproduce

### Expected Behavior

### Actual Behavior

### Evidence

### Suspected Area

### Regression Test Needed
```

## Collaboration Flow

Use this cycle for meaningful project work:

1. Product Manager clarifies the problem, user, scope, non-goals, and acceptance criteria.
2. Development Engineer proposes the implementation approach and affected modules.
3. Test Engineer defines the verification plan before or during implementation.
4. Development Engineer implements the smallest useful change and records test evidence.
5. Test Engineer verifies the change, investigates failures, and records gaps.
6. Operations Manager reviews how the change should be communicated, documented, or promoted.
7. Product Manager writes a stage review and updates the next set of priorities.

For urgent bugs, the Test Engineer may lead first by reproducing the issue, then hand off to Development Engineer for the fix.

## Decision Rules

- If a request changes product behavior, involve Product Manager before implementation.
- If a request changes code, involve Development Engineer and Test Engineer.
- If a request affects README, releases, public positioning, GitHub activity, or contributor onboarding, involve Operations Manager.
- If a request touches Agent Lite, tools, permissions, audit, summaries, artifact context, or device control, apply extra security review.
- If evidence is missing, state the gap instead of turning assumptions into claims.

## ShuFu Safety Boundaries

The team must not introduce:

- Arbitrary shell, Python, JavaScript, or dynamic code execution from model output.
- Model-registered or network-downloaded tools.
- Automatic loading of all artifacts or memory into model context.
- Unapproved side effects.
- Public-network deployment guidance without explicit authentication and risk notes.
- Claims that ESP32 runs local LLMs; ESP32 calls ShuFu Node and exposes bounded device tools.
- Claims that Agent Lite is a general autonomous agent platform.

## Repository Map

- `src/shufu/`: Python CLI, Node, runtime, memory, sync, context, summary, and Agent Lite reference implementation.
- `tests/`: Python unit and compatibility tests.
- `android/`: Android SDK and sample app.
- `esp32/`: ESP-IDF component, examples, and portable C tests.
- `docs/`: product, design, protocol, release, and test reports.
- `outputs/`: verification JSON and preview artifacts.
- `README.md`: public project entry point.
- `CHANGELOG.md`: version evidence and limitations.

## Branch and PR Guidance

- Keep feature work on focused branches.
- Stage only files that belong to the current task.
- Use concise commit messages that describe the user-facing or project-facing change.
- PR descriptions should include what changed, why it changed, and how it was verified.
- Documentation-only changes still need `git diff --check`.

## Evidence Standard

Before any agent reports that work is complete, it must provide fresh evidence:

- For docs: `git diff --check` and a summary of changed files.
- For Python behavior: relevant `python -m unittest ...` commands.
- For Android behavior: relevant Gradle commands.
- For ESP32 C behavior: syntax/build evidence using the available toolchain.
- For GitHub operations: repository URL, branch, PR, or issue links.

If a check cannot run, explain the blocker and residual risk.
