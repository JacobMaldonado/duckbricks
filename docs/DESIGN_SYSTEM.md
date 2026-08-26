# DuckBricks Design System

**Version:** 1.2.0
**Last Updated:** August 25, 2026

A design system for the DuckBricks data platform. This document describes the visual language and styling conventions used across the NiceGUI application, and is the reference for any UI work.

> **Stack note:** DuckBricks is built with **NiceGUI 2.x**, which renders **Quasar 2** components (Vue). Styling is expressed through the NiceGUI Python API — `.classes()` (Quasar utility classes), `.style()` (inline CSS), and `.props()` (Quasar component props) — rather than a separate CSS/Tailwind build. The live icon and color constants live in `app/constants/ui_style.py`.

---

## Table of Contents

1. [Color Palette](#1-color-palette)
2. [Typography](#2-typography)
3. [Spacing & Layout](#3-spacing--layout)
4. [Components](#4-components)
5. [Icons](#5-icons)
6. [UI Patterns & Guidelines](#6-ui-patterns--guidelines)
7. [Accessibility](#7-accessibility)
8. [Code Conventions](#8-code-conventions)

---

## 1. Color Palette

### Primary (Brand)

| Color Name | Hex | RGB | Usage |
|------------|-----|-----|-------|
| **Duck Blue** | `#1976D2` | `rgb(25, 118, 210)` | Primary actions, links, active states |
| **Duck Blue Dark** | `#1565C0` | `rgb(21, 101, 192)` | Primary hover states |
| **Duck Blue Light** | `#E3F2FD` | `rgb(227, 242, 253)` | Selected/hover backgrounds |

`Duck Blue` corresponds to Quasar's default `primary` color (Material Blue 700). It is applied via the `bg-primary` / `text-primary` utility classes.

### Neutral Colors

| Color Name | Hex | Usage |
|------------|-----|-------|
| **Surface** | `#FAFAFA` | Panel/background fills |
| **Surface Alt** | `#F5F5F5` | Subtle fills, chip backgrounds |
| **Border** | `#E0E0E0` | Borders, dividers |
| **Border Alt** | `#DDDDDD` | Secondary borders |
| **Muted** | `#9E9E9E` | Placeholder text, right-aligned metadata |
| **Text Primary** | `#212121` | Body text (`text-grey-9`) |
| **Text Secondary** | `#616161` | Secondary text (`text-grey-7`) |
| **Text Tertiary** | `#9E9E9E` | Tertiary/muted text (`text-grey-5`) |

Neutrals are applied through Quasar's grey utility classes (`bg-grey-1`, `bg-grey-2`, `text-grey-5/7/9`, etc.).

### Semantic Colors

| Color Name | Hex | Usage |
|------------|-----|-------|
| **Error** | `#D32F2F` | Errors, destructive actions, error nodes |
| **Success** | `#21BA45` | Success states (Quasar `positive` default) |
| **Warning** | `#F2C037` | Warnings (Quasar `warning` default) |
| **Info** | `#31CCEC` | Informational messages (Quasar `info` default) |

### Diff / Selection Colors

Used in the Git diff viewer and selection states.

| Color Name | Hex | Usage |
|------------|-----|-------|
| **Diff Added** | `#D1FAE5` | Added-line background |
| **Diff Removed** | `#FEE2E2` | Removed-line background |
| **Diff Hunk** | `#DBEAFE` | Hunk-header background |
| **Selection** | `#BBDEFB` | Selected item background |

---

## 2. Typography

### Font Families

- **Interface text:** Roboto (Quasar's default sans-serif). No custom font is loaded — the browser default sans stack applies.
- **Code / SQL:** System monospace (CodeMirror's default monospace stack) within the SQL editor and diff viewer.

> *Note:* Inter (UI) and JetBrains Mono (code) were proposed in an earlier revision but are **not wired in**. Do not assume custom font families are available.

### Font Sizes

Quasar's responsive typography utilities drive sizes (`text-h6`, `text-subtitle2`, `text-body2`, `text-caption`, etc.).

| Name | Approx. Size | Usage |
|------|--------------|-------|
| **h6** | `20px` | Page/section titles (`text-h6`) |
| **subtitle1** | `16px` | Subheadings (`text-subtitle1`) |
| **subtitle2** | `14px` | Panel headers (`text-subtitle2`) |
| **body1** | `14px` | Default body text |
| **body2** | `14px` | Secondary body text (`text-body2`) |
| **caption** | `12px` | Metadata, badges (`text-caption`) |

### Font Weights

| Weight | Value | Usage |
|--------|-------|-------|
| **Regular** | 400 | Body text, descriptions |
| **Medium** | 500 | Labels, buttons |
| **Bold** | 700 | Headings, emphasis |

---

## 3. Spacing & Layout

### Spacing Scale

Spacing is applied via Quasar spacing utility classes (`q-pa-*`, `q-ma-*`, `q-mx-*`, `q-my-*`, `q-px-*`, `q-py-*`) and `gap-*` classes.

| Token | Value | Class examples |
|-------|-------|----------------|
| `xs` | `4px` | `q-pa-xs`, `q-ma-xs` |
| `sm` | `8px` | `q-pa-sm`, `q-mx-sm` |
| `md` | `16px` | `q-pa-md`, `q-my-md` |
| `lg` | `24px` | `q-pa-lg` |
| `xl` | `32px` | `q-pa-xl` |

### Layout

- **App shell:** `ui.header` (64px) + `ui.left_drawer` (200px, collapsible).
- **Two-panel views:** `ui.splitter` with adjustable split (Query Editor).
- **Metastore Workbench:** three panes for the catalog tree, schema asset list, and asset
  inspector. On narrow screens the panes stack vertically.
- **Jobs dashboard:** responsive KPI cards followed by a searchable operations table; compact
  screens may hide secondary schedule and task-count columns without hiding primary actions.
- **Pipeline editor:** full-page two-column workspace with definition/tasks on the left and a
  persistent flow preview on the right; columns stack on narrow screens.
- **Full-height content:** `height: calc(100vh - 64px)` with `overflow: hidden` on `body` and `.nicegui-content` set to `p-0`.

---

## 4. Components

### Buttons

NiceGUI `ui.button` with Quasar props.

| Variant | Props / Classes | Usage |
|---------|-----------------|-------|
| **Primary** | `color=primary` (or `.props("color=primary")`) | Main actions |
| **Flat** | `.props("flat")` | Subtle/tertiary actions |
| **Dense** | `.props("dense")` | Compact icon buttons |
| **Round** | `.props("round")` | Icon-only buttons |
| **Danger** | `.props("color=negative")` | Destructive actions |

Common modifiers: `flat dense round`, `color=white` (on the header).

### Inputs & Dialogs

- **Inputs:** `ui.input`, `ui.select`, `ui.number` — styled with Quasar defaults.
- **Dialogs:** `ui.dialog` containing `ui.card` with `q-pa-*` padding and an explicit `min-width`
  (`180px`–`700px` depending on content). File or run inspection may use a maximized dialog when
  simultaneous navigation and content preview need most of the viewport.

### Cards & Panels

- **Cards:** `ui.card` with Quasar padding classes (`q-pa-sm`, `q-pa-md`, `q-pa-none`).
- **Panel headers:** `ui.label` with `text-subtitle2 q-pa-sm bg-grey-2`.
- **Borders:** `border: 1px solid #e0e0e0` via `.style()` where an explicit border is needed.

### Navigation

- **Header:** `ui.header().classes("bg-primary text-white items-center")` — brand bar with menu toggle, title, and version label.
- **Drawer:** `ui.left_drawer` with `ui.list` + `ui.item` entries; the active page uses a
  `bg-blue-1` background with primary-colored icon and label. A bottom control switches between
  icons with labels and an icons-only mode that temporarily expands on hover.

### Tables

- **Results grid:** `app/ui/components/results_grid.py` renders query results; right-aligned numeric cells use muted color `#9e9e9e`.
- **Schema display:** table-formatted information-schema metadata in the Metastore Workbench.

### Alerts & Toasts

- **Notifications:** NiceGUI `ui.notify` for transient feedback.
- **Empty/error states:** centered `ui.label` with `text-grey-7`, constrained by `max-width` (e.g., `480px`).

### Badges & Tags

- **Status badges:** Quasar `ui.badge`/`ui.chip` with a mapped Quasar color (see `app/services/git/models.py` for status → color mapping).

---

## 5. Icons

### Icon Library

**Material Icons** (Quasar's default icon set). Icons are referenced by Material icon name via `ui.icon("<name>")` or the `icon=` argument.

### Icons in Use

| Icon | Usage |
|------|-------|
| `storage` | Catalog (top-level namespace) |
| `folder` | Schema (namespace within catalog) |
| `table_chart` | Table |
| `error` | Error nodes / failures |
| `code` | Query Editor nav |
| `schedule` | Jobs nav |
| `folder_open` | Workspace nav |
| `settings` | Settings nav |
| `menu` | Drawer toggle |

The canonical icon mapping lives in `app/constants/ui_style.py` (`TREE_ICONS`).

---

## 6. UI Patterns & Guidelines

### Loading States

- **Lazy loading:** Catalog/schema/table nodes load on expand via `on_expand` handlers (see `app/components/hierarchy_tree.py`).
- **Progress:** Quasar spinners/linear progress for in-flight operations.

### Empty States

- Centered icon + muted heading (`text-grey-7`) + optional description.
- Example: "Select an asset" placeholder in the Metastore Workbench.

### Error States

- `ui.notify` toasts for service errors.
- Error nodes rendered with the `error` icon and `#D32F2F` color.

### Data Visualization Style

- Query results render as a grid/table rather than charts today.
- Job dependencies use a top-to-bottom Mermaid flowchart. Nodes use neutral borders and the
  primary selection palette; the graph is a read-only reflection of the dependency controls.
- Diff coloring uses the semantic diff palette above.

---

## 7. Accessibility

- **Color contrast:** Primary (`#1976D2`) on white meets WCAG AA for large text; body text uses high-contrast grey (`text-grey-9` on white).
- **Icons:** Decorative icons use Material Icons; interactive icon buttons should carry accessible labels.
- **Keyboard:** Rely on Quasar component keyboard support (focus rings, tab order).
- **Labels:** Inputs and icon-only actions should have `aria-label` or visible labels where required.

---

## 8. Code Conventions

### Styling API

Styling is done in Python via NiceGUI's fluent API — no separate CSS build pipeline.

- `.classes(...)` — Quasar utility classes (e.g., `bg-primary`, `q-pa-sm`, `text-grey-7`).
- `.style(...)` — inline CSS for one-off/layout-critical rules (e.g., `height: calc(100vh - 64px)`).
- `.props(...)` — Quasar component props (e.g., `flat dense round`, `width=200`).
- `ui.add_head_html(...)` — page-scoped custom CSS (used in `git_dialog.py`, `query.py`, `workspace.py`).
- `ui.add_static_files(...)` — serve custom JS assets (e.g., `app/ui/static/sql_completion.js`).

### Component Structure

- Reusable UI lives in `app/ui/components/` (flat, one module per component).
- Shared constants (icons, colors) live in `app/constants/ui_style.py`.
- Pages live in `app/ui/pages/`, each rendering through the shared `layout_frame()` shell in `app/ui/components/layout.py`.

### Naming

- Use Quasar/Material naming for colors and spacing tokens.
- Prefer semantic class names over magic hex values; when a hex is required, prefer adding it to `ui_style.py` rather than inlining.

---

## Design Philosophy

DuckBricks design aims to be:

- **Professional yet approachable** — serious data tools that feel human.
- **Clarity over cleverness** — intuitive beats impressive.
- **Consistent and predictable** — patterns users learn once, apply everywhere.
- **Accessible by default** — everyone deserves great UX.

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.1.1 | August 24, 2026 | Documented active-route highlighting and the user-controlled compact navigation mode. |
| 1.1.0 | August 23, 2026 | Aligned to actual NiceGUI/Quasar + Material Icons stack; corrected colors, icons, and code conventions; removed Tailwind/BEM/Lucide references. |
| 1.0.0 | March 14, 2026 | Initial design system release. |
