# DuckBricks Design System

**Version:** 1.0.0  
**Last Updated:** March 14, 2026

A comprehensive design system for the DuckBricks data platform, balancing professional technical aesthetics with modern, approachable user experience patterns inspired by leading data platforms.

---

## Table of Contents

1. [Color Palette](#1-color-palette)
2. [Typography](#2-typography)
3. [Spacing & Layout](#3-spacing--layout)
4. [Components](#4-components)
5. [Icons & Imagery](#5-icons--imagery)
6. [UI Patterns & Guidelines](#6-ui-patterns--guidelines)
7. [Accessibility](#7-accessibility)
8. [Code Conventions](#8-code-conventions)

---

## 1. Color Palette

### Primary Colors (Brand)
The core brand colors represent trust, data, and professionalism.

| Color Name | Hex | RGB | Usage |
|------------|-----|-----|-------|
| **Duck Blue** | `#0066CC` | `rgb(0, 102, 204)` | Primary actions, links, focus states |
| **Duck Blue Dark** | `#004C99` | `rgb(0, 76, 153)` | Primary hover states, emphasis |
| **Duck Blue Light** | `#3385D6` | `rgb(51, 133, 214)` | Subtle highlights, secondary accents |

### Secondary/Accent Colors
Complementary colors for variety and visual interest.

| Color Name | Hex | RGB | Usage |
|------------|-----|-----|-------|
| **Slate Teal** | `#14B8A6` | `rgb(20, 184, 166)` | Secondary actions, data highlights |
| **Slate Purple** | `#8B5CF6` | `rgb(139, 92, 246)` | Special features, premium indicators |
| **Amber Accent** | `#F59E0B` | `rgb(245, 158, 11)` | Highlights, selected states |

### Neutral Colors (Grays & Backgrounds)
Foundational grays for interface structure.

| Color Name | Hex | RGB | Usage |
|------------|-----|-----|-------|
| **Neutral 50** | `#FAFAFA` | `rgb(250, 250, 250)` | Page background (light mode) |
| **Neutral 100** | `#F5F5F5` | `rgb(245, 245, 245)` | Card backgrounds, subtle fills |
| **Neutral 200** | `#E5E5E5` | `rgb(229, 229, 229)` | Borders, dividers |
| **Neutral 300** | `#D4D4D4` | `rgb(212, 212, 212)` | Disabled states, placeholders |
| **Neutral 400** | `#A3A3A3` | `rgb(163, 163, 163)` | Secondary text, icons |
| **Neutral 500** | `#737373` | `rgb(115, 115, 115)` | Tertiary text, muted content |
| **Neutral 600** | `#525252` | `rgb(82, 82, 82)` | Body text (light mode) |
| **Neutral 700** | `#404040` | `rgb(64, 64, 64)` | Headings (light mode) |
| **Neutral 800** | `#262626` | `rgb(38, 38, 38)` | Strong emphasis text |
| **Neutral 900** | `#171717` | `rgb(23, 23, 23)` | Maximum contrast text |
| **White** | `#FFFFFF` | `rgb(255, 255, 255)` | Pure white |
| **Black** | `#000000` | `rgb(0, 0, 0)` | Pure black |

### Semantic Colors
Communicate meaning and status.

| Color Name | Hex | RGB | Usage |
|------------|-----|-----|-------|
| **Success** | `#10B981` | `rgb(16, 185, 129)` | Success states, confirmations |
| **Success Light** | `#D1FAE5` | `rgb(209, 250, 229)` | Success backgrounds |
| **Error** | `#EF4444` | `rgb(239, 68, 68)` | Errors, destructive actions |
| **Error Light** | `#FEE2E2` | `rgb(254, 226, 226)` | Error backgrounds |
| **Warning** | `#F59E0B` | `rgb(245, 158, 11)` | Warnings, cautions |
| **Warning Light** | `#FEF3C7` | `rgb(254, 243, 199)` | Warning backgrounds |
| **Info** | `#3B82F6` | `rgb(59, 130, 246)` | Informational messages |
| **Info Light** | `#DBEAFE` | `rgb(219, 234, 254)` | Info backgrounds |

### Dark Mode Variants
For low-light environments and user preference.

| Color Name | Hex | RGB | Usage |
|------------|-----|-----|-------|
| **Dark BG Primary** | `#0F1419` | `rgb(15, 20, 25)` | Main background (dark mode) |
| **Dark BG Secondary** | `#1A1F26` | `rgb(26, 31, 38)` | Card backgrounds (dark mode) |
| **Dark BG Tertiary** | `#252B33` | `rgb(37, 43, 51)` | Elevated surfaces (dark mode) |
| **Dark Border** | `#30363D` | `rgb(48, 54, 61)` | Borders (dark mode) |
| **Dark Text Primary** | `#E6EDF3` | `rgb(230, 237, 243)` | Body text (dark mode) |
| **Dark Text Secondary** | `#9198A1` | `rgb(145, 152, 161)` | Secondary text (dark mode) |
| **Dark Text Muted** | `#636C76` | `rgb(99, 108, 118)` | Tertiary text (dark mode) |

---

## 2. Typography

### Font Families

#### Primary (UI/Interface)
**Inter** — Modern, highly legible sans-serif for all interface text.
- Fallback: `-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif`
- Source: [Google Fonts](https://fonts.google.com/specimen/Inter)

#### Secondary (Data/Technical)
**JetBrains Mono** — Monospace font for code, SQL, data values, and technical content.
- Fallback: `"SF Mono", Monaco, "Cascadia Code", Consolas, "Courier New", monospace`
- Source: [Google Fonts](https://fonts.google.com/specimen/JetBrains+Mono)

### Font Sizes
Following a modular scale (1.25 ratio) for hierarchy.

| Name | Size | Line Height | Usage |
|------|------|-------------|-------|
| **h1** | `32px` (2rem) | `40px` (1.25) | Page titles |
| **h2** | `28px` (1.75rem) | `36px` (1.29) | Section headers |
| **h3** | `24px` (1.5rem) | `32px` (1.33) | Subsection headers |
| **h4** | `20px` (1.25rem) | `28px` (1.4) | Card titles |
| **h5** | `18px` (1.125rem) | `26px` (1.44) | Minor headings |
| **h6** | `16px` (1rem) | `24px` (1.5) | Smallest headings |
| **body-lg** | `16px` (1rem) | `24px` (1.5) | Large body text |
| **body** | `14px` (0.875rem) | `20px` (1.43) | Default body text |
| **body-sm** | `13px` (0.8125rem) | `18px` (1.38) | Small text, labels |
| **caption** | `12px` (0.75rem) | `16px` (1.33) | Captions, metadata |
| **tiny** | `11px` (0.6875rem) | `14px` (1.27) | Badges, micro-text |

### Font Weights

| Weight | Value | Usage |
|--------|-------|-------|
| **Regular** | 400 | Body text, descriptions |
| **Medium** | 500 | Emphasized text, labels |
| **Semibold** | 600 | Subheadings, buttons |
| **Bold** | 700 | Headings, strong emphasis |

### Letter Spacing
- **Default:** `0` (normal tracking)
- **Headings (h1-h3):** `-0.02em` (tighter, more elegant)
- **Uppercase text:** `0.05em` (improved readability)
- **Monospace code:** `0` (preserve alignment)

---

## 3. Spacing & Layout

### Spacing Scale (8pt Grid)
All spacing follows multiples of 4px for consistency.

| Token | Value | Usage |
|-------|-------|-------|
| `space-1` | `4px` | Tight spacing, icon gaps |
| `space-2` | `8px` | Small padding, compact layouts |
| `space-3` | `12px` | Standard padding (buttons, inputs) |
| `space-4` | `16px` | Default spacing unit |
| `space-5` | `20px` | Medium spacing |
| `space-6` | `24px` | Large padding, card spacing |
| `space-8` | `32px` | Section spacing |
| `space-10` | `40px` | Large section spacing |
| `space-12` | `48px` | Extra-large spacing |
| `space-16` | `64px` | Page-level spacing |
| `space-20` | `80px` | Hero section spacing |
| `space-24` | `96px` | Maximum spacing |

### Grid System
12-column responsive grid with flexible gutters.

| Breakpoint | Columns | Gutter | Container Width |
|------------|---------|--------|-----------------|
| **Mobile** (< 640px) | 4 | 16px | 100% (fluid) |
| **Tablet** (640px - 1023px) | 8 | 24px | 100% (fluid) |
| **Desktop** (1024px - 1279px) | 12 | 24px | 1024px (max) |
| **Wide** (≥ 1280px) | 12 | 32px | 1280px (max) |

### Breakpoints
Mobile-first approach with min-width media queries.

| Name | Value | Usage |
|------|-------|-------|
| `sm` | `640px` | Small tablets |
| `md` | `768px` | Tablets, small laptops |
| `lg` | `1024px` | Desktops |
| `xl` | `1280px` | Large desktops |
| `2xl` | `1536px` | Ultra-wide displays |

### Container Widths
- **Full:** `100%` — Edge-to-edge
- **Wide:** `1280px` — Primary content container
- **Standard:** `1024px` — Comfortable reading width
- **Narrow:** `768px` — Forms, articles
- **Text:** `640px` — Optimal reading line length

---

## 4. Components

### Buttons

#### Variants
| Variant | Background | Text Color | Border | Usage |
|---------|------------|------------|--------|-------|
| **Primary** | Duck Blue | White | None | Main actions |
| **Secondary** | Neutral 100 | Neutral 700 | Neutral 200 | Secondary actions |
| **Ghost** | Transparent | Neutral 700 | None | Tertiary actions |
| **Danger** | Error | White | None | Destructive actions |
| **Success** | Success | White | None | Confirmations |

#### Sizes
| Size | Height | Padding (x-axis) | Font Size | Icon Size |
|------|--------|------------------|-----------|-----------|
| **Small** | 32px | 12px | 13px | 16px |
| **Medium** | 40px | 16px | 14px | 20px |
| **Large** | 48px | 24px | 16px | 24px |

#### States
- **Default:** Base styling
- **Hover:** Darken background by 10%, add subtle shadow
- **Active:** Darken background by 15%, inner shadow
- **Disabled:** 50% opacity, no hover effects, cursor not-allowed
- **Loading:** Show spinner, disable interactions

### Form Inputs

#### Text Input
- **Height:** 40px (medium), 32px (small), 48px (large)
- **Border:** 1px solid Neutral 200
- **Border Radius:** 6px
- **Padding:** 12px (horizontal), 10px (vertical)
- **Font:** Body (14px)
- **Focus:** 2px Duck Blue outline, border changes to Duck Blue

#### Select Dropdown
- Same styling as text input
- Chevron icon (20px) on the right, 12px from edge

#### Checkbox & Radio
- **Size:** 20px × 20px
- **Border:** 2px solid Neutral 300
- **Border Radius:** 4px (checkbox), 50% (radio)
- **Checked:** Duck Blue background, white checkmark/dot

#### Textarea
- Same styling as text input
- **Min height:** 80px
- **Resizable:** Vertical only

#### States
- **Default:** Neutral 200 border
- **Focus:** Duck Blue border + outline
- **Error:** Error border, Error text helper
- **Disabled:** Neutral 100 background, Neutral 300 text
- **Read-only:** Neutral 50 background, no border changes on focus

### Cards & Panels

#### Card
- **Background:** White (light), Dark BG Secondary (dark)
- **Border:** 1px solid Neutral 200 (light), Dark Border (dark)
- **Border Radius:** 8px
- **Padding:** 24px (default), 16px (compact)
- **Shadow:** `0 1px 3px rgba(0, 0, 0, 0.1)`
- **Hover:** Lift shadow to `0 4px 8px rgba(0, 0, 0, 0.12)`

#### Panel (Sidebar/Container)
- **Background:** Neutral 50 (light), Dark BG Primary (dark)
- **Border:** 1px solid Neutral 200 (light), Dark Border (dark)
- **Padding:** 16px - 32px depending on content

### Navigation

#### Navigation Bar
- **Height:** 64px
- **Background:** White (light), Dark BG Secondary (dark)
- **Border Bottom:** 1px solid Neutral 200 (light), Dark Border (dark)
- **Padding:** 16px (horizontal)
- **Logo:** Left-aligned, 32px height
- **Links:** Neutral 600 (light), Dark Text Secondary (dark), Duck Blue on active

#### Breadcrumbs
- **Font:** Body-sm (13px)
- **Color:** Neutral 500
- **Separator:** `/` or `›` (Neutral 300)
- **Active:** Neutral 700, no link

#### Tabs
- **Height:** 48px
- **Border Bottom:** 2px solid Neutral 200
- **Active Tab:** 2px Duck Blue border bottom, Duck Blue text
- **Inactive Tab:** Neutral 600 text, hover → Neutral 700

### Modals & Dialogs

#### Modal
- **Overlay:** `rgba(0, 0, 0, 0.5)` backdrop
- **Container:** Card styling, max-width 600px (default)
- **Header:** 24px padding, border-bottom (Neutral 200)
- **Body:** 24px padding
- **Footer:** 16px padding, border-top (Neutral 200), buttons right-aligned
- **Close Button:** Top-right, 32px × 32px, ghost style

#### Sizes
| Size | Max Width |
|------|-----------|
| Small | 400px |
| Medium | 600px |
| Large | 800px |
| Full | 95vw |

### Tables

#### Table Structure
- **Header:** Neutral 100 background, Semibold (600) text, Neutral 700
- **Row:** White background, 1px border-bottom Neutral 200
- **Row Hover:** Neutral 50 background
- **Row Active/Selected:** Info Light background
- **Cell Padding:** 12px (vertical), 16px (horizontal)
- **Font:** Body (14px) for data, Body-sm (13px) for metadata

#### Sortable Headers
- Clickable, cursor pointer
- Show sort icon (chevron up/down) on hover and active
- Active sort: Duck Blue text + icon

### Alerts & Toasts

#### Alert (Inline)
- **Padding:** 12px 16px
- **Border Radius:** 6px
- **Border:** 1px solid (matches variant color)
- **Icon:** Left-aligned, 20px
- **Variants:** Success, Error, Warning, Info (use semantic colors + light backgrounds)

#### Toast (Notification)
- **Width:** 360px (max)
- **Position:** Top-right or bottom-right
- **Shadow:** `0 4px 12px rgba(0, 0, 0, 0.15)`
- **Animation:** Slide in from right, fade out
- **Duration:** 5 seconds (default), persist on hover
- Same styling as Alert

### Badges & Tags

#### Badge
- **Size:** 20px height (small), 24px height (medium)
- **Padding:** 4px 8px
- **Border Radius:** 12px (pill shape)
- **Font:** Tiny (11px), Semibold (600)
- **Variants:** Primary (Duck Blue), Success, Error, Warning, Info, Neutral

#### Tag (Removable)
- Same as Badge, but with close icon (16px) on the right
- 4px gap between text and icon

---

## 5. Icons & Imagery

### Icon Library
**Lucide Icons** — Clean, consistent, open-source icon set.
- Homepage: [https://lucide.dev](https://lucide.dev)
- License: ISC (permissive)
- Style: Outline, 2px stroke width

### Icon Sizes
| Size | Value | Usage |
|------|-------|-------|
| **xs** | `14px` | Inline with small text |
| **sm** | `16px` | Inline with body text, badges |
| **md** | `20px` | Buttons, inputs, default usage |
| **lg** | `24px` | Headers, feature icons |
| **xl** | `32px` | Hero sections, empty states |
| **2xl** | `48px` | Large empty states |

### Logo Usage
- **Full Logo:** Use on navigation bar (left), footer
- **Icon-only:** Use in favicons, mobile headers (< 640px)
- **Minimum Size:** 24px height (icon), 120px width (full logo)
- **Clear Space:** Minimum 16px padding around logo
- **Color:** Duck Blue (primary), White (on dark backgrounds)

### Empty State Illustrations
- **Style:** Simple, friendly line illustrations
- **Color:** Neutral 300 (outlines), Neutral 100 (fills), Duck Blue Light (accents)
- **Size:** 200px - 400px width
- **Usage:** No results, no data, first-time experiences

---

## 6. UI Patterns & Guidelines

### Loading States

#### Spinner (Inline)
- **Size:** 20px (default), 16px (small), 24px (large)
- **Color:** Duck Blue
- **Animation:** Smooth rotation (1s duration, infinite)

#### Skeleton Loader
- **Background:** Neutral 100 (light), Dark BG Tertiary (dark)
- **Animation:** Shimmer effect (left-to-right wave)
- **Use:** Complex layouts, data tables, card grids

#### Progress Bar
- **Height:** 8px
- **Background:** Neutral 200
- **Fill:** Duck Blue (determinate), animated gradient (indeterminate)
- **Border Radius:** 4px

### Empty States
- **Icon:** 2xl size (48px), Neutral 400 color
- **Heading:** h4, Neutral 700
- **Description:** Body, Neutral 500, max-width 400px
- **Action:** Primary button (when applicable)
- **Illustration:** Optional, centered

### Error States
- **Color:** Error
- **Icon:** Error icon (alert-circle), 24px
- **Message:** Body-sm, Error text, clear explanation
- **Action:** Retry button or help link

### Form Validation Feedback
- **Inline Errors:** Below input, Error text, body-sm
- **Success Indicators:** Green checkmark icon in input (right)
- **Error Indicators:** Red X icon or highlight input border
- **Validation Timing:** On blur (first) or on submit, then live on change

### Data Visualization Style
- **Charts:** Clean, minimal gridlines
- **Colors:** Use semantic colors + secondary palette
- **Tooltips:** Card styling, 8px offset from cursor
- **Legends:** Body-sm font, inline or below chart
- **Axes:** Neutral 500 text, Neutral 200 lines

---

## 7. Accessibility

### Color Contrast Ratios (WCAG 2.1)
All text meets **WCAG AA** standards minimum; critical UI meets **AAA** where possible.

| Combination | Contrast Ratio | Standard |
|-------------|----------------|----------|
| Neutral 700 on White | 10.7:1 | AAA |
| Neutral 600 on White | 7.5:1 | AAA |
| Neutral 500 on White | 4.9:1 | AA Large |
| Duck Blue on White | 5.3:1 | AA |
| White on Duck Blue | 5.3:1 | AA |
| Dark Text Primary on Dark BG Primary | 13.2:1 | AAA |

### Keyboard Navigation Guidelines
- **Tab Order:** Logical, follows visual hierarchy
- **Focus Indicators:** 2px Duck Blue outline (offset 2px), visible on all interactive elements
- **Skip Links:** "Skip to main content" link at page top (visible on focus)
- **Keyboard Shortcuts:** Document all shortcuts, avoid single-key bindings (except modals/editors)

### Screen Reader Considerations
- **Semantic HTML:** Use proper heading hierarchy, landmarks (`<nav>`, `<main>`, `<aside>`)
- **ARIA Labels:** Add to icon-only buttons, decorative elements marked `aria-hidden="true"`
- **Form Labels:** All inputs have visible or `aria-label` labels
- **Live Regions:** Use `aria-live` for dynamic content (alerts, notifications)

### Focus States
- **Visible Outline:** 2px solid Duck Blue, 2px offset
- **Never Remove:** Don't use `outline: none` without replacement
- **Custom Focus Rings:** Use box-shadow for more control (e.g., `0 0 0 2px #0066CC`)

---

## 8. Code Conventions

### CSS Naming Conventions
**Utility-First with Tailwind CSS** — Use Tailwind's utility classes as the primary styling method.

- **Custom Components:** Use semantic class names when building reusable components (e.g., `.btn-primary`, `.card`, `.input-field`)
- **BEM for Custom CSS:** When writing custom CSS, follow BEM naming:
  - Block: `.card`
  - Element: `.card__header`
  - Modifier: `.card--elevated`

### Component Structure
- **Atomic Design:** Build from atoms → molecules → organisms → templates → pages
- **File Organization:**
  ```
  components/
    atoms/          (buttons, inputs, icons)
    molecules/      (form fields, cards)
    organisms/      (navigation, tables, modals)
    templates/      (page layouts)
  ```
- **Single Responsibility:** Each component does one thing well

### CSS Variable Naming
Use CSS custom properties for theme values:

```css
:root {
  /* Colors */
  --color-primary: #0066CC;
  --color-primary-dark: #004C99;
  --color-neutral-50: #FAFAFA;
  
  /* Spacing */
  --space-1: 4px;
  --space-4: 16px;
  
  /* Typography */
  --font-sans: 'Inter', -apple-system, sans-serif;
  --font-mono: 'JetBrains Mono', monospace;
  --text-base: 14px;
  
  /* Borders */
  --radius-sm: 4px;
  --radius-md: 6px;
  --radius-lg: 8px;
}
```

### Responsive Design Patterns
- **Mobile-First:** Write base styles for mobile, add complexity with `min-width` media queries
- **Container Queries:** Use where appropriate for component-level responsiveness
- **Fluid Typography:** Use `clamp()` for smooth scaling:
  ```css
  font-size: clamp(14px, 2vw, 16px);
  ```

---

## Design Philosophy

DuckBricks design aims to be:
- **Professional yet Approachable** — Serious data tools that feel human
- **Clarity over Cleverness** — Intuitive beats impressive
- **Consistent and Predictable** — Patterns users can learn once, apply everywhere
- **Accessible by Default** — Everyone deserves great UX
- **Performance-Conscious** — Fast load times, smooth interactions

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | March 14, 2026 | Initial design system release |

---

**Maintained by the DuckBricks Design Team**  
Questions? Contact the team or open an issue in the repository.
