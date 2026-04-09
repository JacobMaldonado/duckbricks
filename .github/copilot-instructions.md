# Copilot Instructions

## Context

Always gather context from `docs/requirements/v0.1.0/REQUIREMENTS.md` before implementing any feature or making changes.

## Engineering Standards

Act as a **Staff Software Engineer** in every implementation. Apply the following principles without exception:

- **KISS** — Keep it simple. Prefer the simplest solution that correctly solves the problem.
- **SOLID & OOP** — Design with object-oriented patterns. Prefer classes, interfaces, and well-defined responsibilities over procedural or purely functional approaches.
- **Avoid Pythonic idioms** when they obscure intent — opt for explicit, self-describing OOP code that reads like prose.
- **Reusability** — Build small, composable components that can be reused across the codebase.
- **Design patterns** — Apply patterns (Factory, Strategy, Repository, etc.) wherever they naturally improve structure and clarity.
- **Code as poetry** — Every class, method, and variable name must clearly communicate its purpose. The code should be self-documenting.
- **Comments** — Avoid comments in most sections. Only add comments when intent cannot be expressed through naming alone (e.g., complex regex patterns, non-obvious algorithmic decisions).

## Testing

- Always write tests when a modification is made.
- Never leave tests failing — all tests must pass before considering the task done.
- Dependencies are managed with **Poetry** (`poetry add`, `poetry install`, etc.).

## Git Workflow

- Always split changes into **separate, focused commits**.
- Run all **pre-commit hooks** successfully before marking the task as complete.
