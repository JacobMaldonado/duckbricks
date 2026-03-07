# DuckBricks v0.1.0 — Requirements

## 🦆 Project Overview

**DuckBricks** is a self-hosted platform that mimics Databricks functionality using [Ducklake](https://ducklake.select/docs/stable) as its engine.

## 🎯 v0.1.0 Scope

The goal of this initial release is to establish the core infrastructure, continuous integration, and basic user interface.

### Core Features

#### 1. Basic Portal

A lightweight, unified web interface for the application.

**Acceptance Criteria:**

- [ ] A single-page application served via NiceGUI
- [ ] Navigation between Metastore Explorer and Execution Environment views
- [ ] Clean, responsive layout

#### 2. Basic Metastore Explorer

- View a list of all tables available in the Ducklake metastore.
- Inspect table schemas (check structure and column `dtypes`).

**Acceptance Criteria:**

- [ ] Displays a list of all tables in the metastore
- [ ] Clicking a table shows its schema (column names, data types)
- [ ] Handles empty metastore gracefully (no tables)

#### 3. Basic Execution Environment

- A dedicated, separate view for querying.
- Ability to write and execute SQL queries directly against the tables in the metastore.

**Acceptance Criteria:**

- [ ] Dedicated query view, separate from the Metastore Explorer
- [ ] Text area / editor for writing SQL
- [ ] Execute button that runs the query against the metastore
- [ ] Results displayed in a table format
- [ ] Errors displayed clearly to the user

## 🛠 Technical Specifications

### Framework

- The UI and backend must be built using [NiceGUI](https://nicegui.io/).
- Code must maintain a **strict separation of concerns** — keep UI components separate from Ducklake execution logic.

### Dependency Management

- All dependencies must be strictly managed using **Poetry**.
- No `requirements.txt` for production deps — Poetry's `pyproject.toml` and `poetry.lock` are the source of truth.

### Testing

- Every feature must be accompanied by unit tests using `pytest`.
- Tests must be runnable via `pytest` from the project root.

### Pre-commit Hooks

Code quality must be enforced locally prior to commits using the following hooks:

| Hook | Purpose |
|------|---------|
| **Ruff** | Linting and formatting (replaces Black/Flake8/isort) |
| **Mypy** | Static type checking |
| `trailing-whitespace` | Remove trailing whitespace |
| `end-of-file-fixer` | Ensure files end with newline |
| `check-yaml` | Validate YAML files |
| `check-toml` | Validate TOML files |
| `check-added-large-files` | Prevent large files from being committed |

## 🌿 Development Workflow & CI/CD

### Branching Strategy

1. Create a dedicated `feature/<feature-name>` branch off of the `dev` branch.
2. Develop the feature, write passing unit tests, and ensure pre-commit hooks pass locally.
3. Open a Pull Request (PR) targeting the `dev` branch.

### Continuous Integration (GitHub Actions)

A CI pipeline must run automatically on every PR to `dev`. The PR **cannot be merged** unless the Action successfully runs:

- `poetry install`
- `pre-commit run --all-files`
- `pytest`

### Code Review

- Wait for code review and explicit approval before merging.

## 📋 Feature Priority

| # | Feature | Priority |
|---|---------|----------|
| 1 | CI/CD Pipeline + Pre-commit + Poetry setup | **High** |
| 2 | Basic Portal (NiceGUI shell) | **High** |
| 3 | Basic Metastore Explorer | **High** |
| 4 | Basic Execution Environment | **High** |

All features are required for v0.1.0 release.
