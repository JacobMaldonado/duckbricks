# Technical Review Backlog

**Review snapshot:** 2026-08-24  
**Baseline:** `f6fd7af`  
**Status:** Proposed work; each item needs its own implementation plan

This file preserves the recommendations that remain after the deployment defaults, startup
readiness, validation gates, and related architecture documentation were corrected. It is a
planning aid, not a replacement for [`ARCHITECTURE.md`](ARCHITECTURE.md).

## Recommended Order

1. Secure filesystem and Git boundaries before exposing DuckBricks to untrusted users.
2. Define and enforce the authentication and network trust boundary.
3. Make database and container upgrades reproducible.
4. Reconcile the architecture document with the implemented system.
5. Refactor the largest UI modules after their behavior is protected by tests.

## P0 — Security Boundaries

### SEC-001: Enforce workspace path containment

**Finding:** `WorkspaceService._resolve_safe()` compares string prefixes. A sibling such as
`workspace-escape` can share the workspace path prefix without being inside the workspace.
Rename destinations are built from an unchecked `new_name`, and Git folder/operation services
also join caller-provided paths directly to the workspace root.

**Suggested change:**

- Introduce one reusable workspace path resolver based on resolved `Path` containment
  (`relative_to()` or `is_relative_to()`), rather than string comparison.
- Use it in `WorkspaceService`, `GitFolderService`, and `GitOperationsService`.
- Validate both source and destination paths for rename, move, clone, discard, diff, stage,
  repository registration, and repository creation operations.
- Reject absolute paths, traversal segments, path separators in a rename-only name, workspace-root
  destructive operations, and symlink escapes.
- Add tests for sibling-prefix paths, `..`, absolute paths, malicious rename values, and symlinks.

**Done when:** No file or Git operation can read, write, move, delete, or initialize anything
outside the configured workspace root.

### SEC-002: Remove Git credentials from repository metadata and command output

**Finding:** `GitHubPatProvider.clone()` passes a token-bearing URL to `git clone`. Git can retain
that URL as `remote.origin.url` in `.git/config`. Authenticated URLs are also passed directly to
Git subprocesses for other remote operations.

**Suggested change:**

- Authenticate clones without making the credential the persisted origin, or immediately replace
  the origin with the clean provider URL before returning from the operation.
- Use a short-lived credential mechanism for fetch, pull, and push; keep tokens out of command
  arguments where practical.
- Redact credentials from exceptions, logs, and UI notifications.
- Sanitize existing registered repositories whose origin contains credentials.
- Add tests asserting that `.git/config`, logs, and raised errors never contain a token.

**Done when:** A repository cloned or operated on through DuckBricks contains only a credential-free
origin URL and no credential is exposed through application output.

### SEC-003: Add authentication and authorization before multi-user deployment

**Finding:** The current architecture intentionally runs in unauthenticated single-user mode.
DuckBricks exposes SQL execution, jobs, workspace files, notebooks, and Git operations, so it must
not be treated as a safe multi-user or internet-facing service yet.

**Suggested change:**

- Document the supported trust boundary and threat model first.
- Add session authentication for the NiceGUI application and explicit protection for FastAPI,
  WebSocket, Prefect proxy, and Marimo proxy routes.
- Add authorization around destructive operations before implementing full workspace RBAC.
- Define session expiry, logout, bootstrap-admin, password reset, and secret rotation behavior.
- Add route-level and service-level authorization tests, including proxy bypass attempts.

**Done when:** Every privileged surface has a defined identity and permission check, and the
documented single-user limitation can be removed.

### SEC-004: Minimize default network exposure

**Finding:** Docker Compose publishes PostgreSQL and Prefect ports to the host in addition to the
DuckBricks web port. These mappings are useful for local administration but broaden the default
attack surface.

**Suggested change:**

- Keep internal services on the Compose network by default.
- Move optional host port mappings to a development/admin profile or bind them to loopback.
- Document TLS and reverse-proxy requirements for non-local deployments.
- Review whether the Prefect and Marimo proxies should be enabled before authentication exists.

**Done when:** The default deployment publishes only the intended user-facing entry point and
production exposure requirements are explicit.

## P1 — Reproducibility and Persistence

### OPS-001: Pin container artifacts

**Finding:** Compose uses moving image tags such as `prefecthq/prefect:3-latest` and
`python:3.12-slim`. Rebuilding the same commit can therefore produce a different runtime.

**Suggested change:**

- Pin third-party images to reviewed patch versions and, for releases, immutable digests.
- Record a deliberate dependency-update process and verify upgrades in CI.
- Keep the application image and worker image on the same dependency set.

**Done when:** A release can be rebuilt with the same container inputs and upgrades are explicit.

### DB-001: Adopt Alembic as the database migration authority

**Finding:** Alembic is a dependency and the architecture describes Alembic migrations, but startup
currently runs `Base.metadata.create_all()` plus inline `ALTER TABLE` statements in
`app/services/database/session.py`. There is no migrations directory.

**Suggested change:**

- Create an Alembic baseline that supports both new and existing installations.
- Convert the inline additive changes into versioned migrations.
- Run `alembic upgrade head` as an explicit startup/deployment step.
- Add upgrade tests from the supported prior schema and a clean-database test.
- Remove the inline migration function after compatibility is verified.

**Done when:** Schema state is versioned, reviewable, repeatable, and upgrade-tested.

### CI-001: Exercise the container contract in CI

**Finding:** Unit tests and static checks cover Python behavior, while the complete Compose startup
and readiness flow is currently verified manually.

**Suggested change:**

- Add a bounded Compose smoke test that builds the images, waits for health, checks liveness and
  readiness, and tears the stack down.
- Preserve service logs as CI artifacts when startup or readiness fails.

**Done when:** Changes to images, environment defaults, health checks, or service wiring cannot
merge without exercising the deployed topology.

## P2 — Architecture and Documentation Accuracy

### DOC-001: Separate implemented architecture from target architecture

**Finding:** `ARCHITECTURE.md` still presents several planned elements as current in its database
schema and data-flow sections. Examples include the PostgreSQL metastore mirror/sync job,
users/workspaces/RBAC tables, broad catalog/query REST endpoints, and automatic Alembic migrations.
ADR-002 also describes a metadata mirror that is not implemented.

**Suggested change:**

- Label each major capability as implemented, planned, or superseded.
- Update diagrams and flows to match the current DuckLake/PostgreSQL source-of-truth model.
- Reconcile ADR-002 through a superseding ADR instead of silently rewriting the decision history.
- Keep future API, multi-tenancy, and metastore-mirror designs in explicitly marked target sections.

**Done when:** A new contributor can distinguish deployed behavior from future design without
reading the implementation.

### API-001: Decide the intended FastAPI surface

**Finding:** The health endpoints and service proxies are implemented, while the broader REST API
described in the architecture remains planned.

**Suggested change:**

- Decide whether DuckBricks will expose a supported programmatic API in the next milestone.
- If yes, define versioning, authentication, error contracts, schemas, and service-layer boundaries
  before adding endpoints.
- If no, narrow the architecture claims and treat FastAPI as the NiceGUI host plus operational
  endpoints.

**Done when:** The public API boundary is explicit and documentation matches the supported surface.

## P3 — Maintainability

### UI-001: Split large page modules along UI responsibilities

**Finding:** Workspace and query pages combine rendering, dialogs, event handling, state, and
service coordination in large modules. This increases regression risk as features accumulate.

**Suggested change:**

- Extract cohesive components and controllers/view models without changing user behavior.
- Start with workspace Git dialogs/actions and query tab/editor coordination.
- Add focused behavior tests before moving each responsibility.
- Continue following `DESIGN_SYSTEM.md` for all extracted UI components.

**Done when:** Page entry points primarily compose tested components instead of owning unrelated
workflows.

### CORE-001: Make service dependencies explicit

**Finding:** Several UI and service modules construct process-wide service instances at import
time. This hides lifecycle and configuration choices and makes isolated testing harder.

**Suggested change:**

- Introduce small composition-root factories for application, request, or page-scoped services.
- Pass database sessions, providers, and workspace policies through constructors where useful.
- Avoid a framework-wide dependency-injection rewrite; migrate one bounded workflow at a time.

**Done when:** Core workflows can be tested with explicit dependencies and no import-time external
state.

## Completed During the Original Review

The following findings are intentionally excluded from the remaining backlog:

- Container-aware environment defaults and corrected internal web port.
- Fail-fast configuration validation and dependency startup retries.
- Liveness/readiness endpoints and Compose health wiring.
- Passing test, Ruff, formatting, mypy, pre-commit, and Compose validation gates.
- Deployment and health documentation aligned with the current five-service topology.

