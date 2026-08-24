# Copilot Instructions

## Context

Before implementing any feature or making any change, read and follow:

- `docs/ARCHITECTURE.md` — system design, component responsibilities, and data flow.
- `docs/DESIGN_SYSTEM.md` — UI styling conventions, colors, icons, and component patterns.

If a request conflicts with (or drifts from) either document, **stop and flag the drift to the user**. Do not proceed silently. Ask the user whether they want to:

1. Update the affected document(s) to reflect the new direction, or
2. Take a different approach that stays consistent with the existing documents.

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
