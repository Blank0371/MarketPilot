# Repository Guidelines

## Project Structure & Module Organization
This repository is currently MVP-planning focused.

- `codex_data_engineer_agent_mvp_plan.md`: primary architecture and implementation plan for the Data Engineer Agent.
- `.gitignore`: ignore rules (currently minimal).

When implementation files are added, keep a predictable layout:

- `app/`: runtime code (agents, planners, adapters, validators).
- `tests/`: unit and integration tests mirroring `app/` paths.
- `docs/`: design notes and ADR-style decisions.
- `scripts/`: local automation (data checks, dev helpers).

## Build, Test, and Development Commands
No build/test toolchain is committed yet. Until then, use lightweight checks:

- `git status` — verify only intended files changed.
- `rg --files` — list tracked source files quickly.
- `rg "TODO|FIXME"` — scan for unresolved work markers.

If/when Python code is added, standardize on commands documented in `README` (for example: `pytest`, `ruff check`, `ruff format`).

## Coding Style & Naming Conventions
For new Python modules, use these defaults unless the repo later defines stricter rules:

- 4-space indentation, UTF-8, LF line endings.
- `snake_case` for functions/files, `PascalCase` for classes, `UPPER_SNAKE_CASE` for constants.
- Keep modules focused: one responsibility per file.
- Prefer explicit types and small, testable functions.

For Markdown docs:

- Use clear section headings.
- Keep examples executable or copy-pasteable.
- Update architecture docs when behavior changes.

## Testing Guidelines
A formal test suite is not present yet. Add tests alongside feature work.

- Place tests under `tests/` with names like `test_<module>.py`.
- Cover parser/normalization logic, source selection, and validation edge cases.
- Prefer deterministic tests with fixed fixtures over live API calls.

## Commit & Pull Request Guidelines
Follow the existing history style:

- Use concise, intent-first messages, commonly Conventional Commit style (`feat:`, `chore:`), optionally scoped (for example `feat(block4): ...`).
- Keep commits focused to one change set.
- In PRs, include: purpose, key files changed, test evidence, and any follow-up tasks.
- Link relevant issue/task IDs when available.

## Security & Data Integrity Notes
- Do not hardcode secrets or API keys in source/docs.
- Do not invent datasets or endpoints; only use verified sources listed in project docs.
- Preserve provenance: record source URLs and known limitations for produced data.
