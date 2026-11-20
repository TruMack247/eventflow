---
name: Slate Orchestrator
colors:
  surface: '#f9f9ff'
  surface-dim: '#d7dae3'
  surface-bright: '#f9f9ff'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#f1f3fd'
  surface-container: '#ebeef7'
  surface-container-high: '#e5e8f2'
  surface-container-highest: '#dfe2ec'
  on-surface: '#181c23'
  on-surface-variant: '#464554'
  inverse-surface: '#2d3138'
  inverse-on-surface: '#eef0fa'
  outline: '#767586'
  outline-variant: '#c7c4d7'
  surface-tint: '#4a4bd3'
  primary: '#4041c9'
  on-primary: '#ffffff'
  primary-container: '#5a5ce3'
  on-primary-container: '#f2efff'
  inverse-primary: '#c1c1ff'
  secondary: '#5b5f65'
  on-secondary: '#ffffff'
  secondary-container: '#dfe2ea'
  on-secondary-container: '#61656b'
  tertiary: '#83450a'
  on-tertiary: '#ffffff'
  tertiary-container: '#a15c22'
  on-tertiary-container: '#ffede3'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#e1e0ff'
  primary-fixed-dim: '#c1c1ff'
  on-primary-fixed: '#07006c'
  on-primary-fixed-variant: '#302fbb'
  secondary-fixed: '#dfe2ea'
  secondary-fixed-dim: '#c3c6ce'
  on-secondary-fixed: '#181c21'
  on-secondary-fixed-variant: '#43474d'
  tertiary-fixed: '#ffdcc5'
  tertiary-fixed-dim: '#ffb782'
  on-tertiary-fixed: '#301400'
  on-tertiary-fixed-variant: '#703800'
  background: '#f9f9ff'
  on-background: '#181c23'
  surface-variant: '#dfe2ec'
typography:
  headline-xl:
    fontFamily: Inter
    fontSize: 32px
    fontWeight: '600'
    lineHeight: 40px
    letterSpacing: -0.02em
  headline-lg:
    fontFamily: Inter
    fontSize: 24px
    fontWeight: '600'
    lineHeight: 32px
    letterSpacing: -0.015em
  headline-md:
    fontFamily: Inter
    fontSize: 18px
    fontWeight: '600'
    lineHeight: 24px
    letterSpacing: -0.01em
  headline-sm:
    fontFamily: Inter
    fontSize: 15px
    fontWeight: '600'
    lineHeight: 20px
    letterSpacing: -0.005em
  body-lg:
    fontFamily: Inter
    fontSize: 15px
    fontWeight: '400'
    lineHeight: 22px
    letterSpacing: 0em
  body-md:
    fontFamily: Inter
    fontSize: 13px
    fontWeight: '400'
    lineHeight: 18px
    letterSpacing: 0em
  body-sm:
    fontFamily: Inter
    fontSize: 12px
    fontWeight: '400'
    lineHeight: 16px
    letterSpacing: 0.005em
  label-code-md:
    fontFamily: JetBrains Mono
    fontSize: 12px
    fontWeight: '500'
    lineHeight: 16px
    letterSpacing: -0.01em
  label-code-sm:
    fontFamily: JetBrains Mono
    fontSize: 11px
    fontWeight: '500'
    lineHeight: 14px
    letterSpacing: -0.005em
  label-caps:
    fontFamily: Inter
    fontSize: 11px
    fontWeight: '600'
    lineHeight: 14px
    letterSpacing: 0.04em
rounded:
  sm: 0.25rem
  DEFAULT: 0.5rem
  md: 0.75rem
  lg: 1rem
  xl: 1.5rem
  full: 9999px
spacing:
  gutter: 1rem
  gutter-dense: 0.5rem
  margin: 1.5rem
  margin-mobile: 1rem
  space-2xs: 0.125rem
  space-xs: 0.25rem
  space-sm: 0.5rem
  space-md: 0.75rem
  space-lg: 1rem
  space-xl: 1.5rem
  space-2xl: 2rem
---

## Brand & Style

This design system embodies the precision, composure, and structural rigor demanded by mission-critical project logistics. Engineered for complex timeline dependency graphs and event operations, the system balances dense technical tooling with quiet executive polish—reminiscent of high-utility desktop workflows like Linear, Cron, and Stripe Dashboard.

### Aesthetic Persona
- **Disciplined Precision:** Every element aligns to strict layout grids. Visual weight communicates state, dependency chains, and immediate actions rather than ornamental flourish.
- **Architectural Clarity:** Flat canvas surfaces combined with crisp 1px hairlines establish depth through boundary definition and tonal hierarchy rather than heavy artificial shadows.
- **Micro-State Observability:** Critical task chains (Blocked, In-Progress, Ready, Scheduled) utilize high-legibility micro-badges, status pips, and monospaced telemetry to guarantee immediate situational awareness.

## Colors

The palette is anchored on high-legibility neutrals with high-chroma, purposeful accents reserved strictly for functional signals and semantic states.

### Core Semantic Roles
- **Primary (`#5A5CE3`):** Primary interactions, commit triggers, dependency node links, active navigational tabs, and focused canvas states.
- **Primary Soft (`#EFF1FF`):** Selected table rows, highlighted timeline tracks, and focused container fills.
- **Secondary (`#2D3137`):** Structural control buttons, contextual toolbar chips, and secondary administrative toggles.
- **Tertiary (`#C2773B`):** Milestone markers, schedule run-rate metrics, category clusters, and analytical charts.
- **Background (`#FAFBFD`):** Canvas backdrop across desktop panes and scroll areas.
- **Surface (`#FFFFFF`):** High-level task cards, flyout side-drawers, and contextual menus.
- **Surface 2 (`#F4F5F8`):** Inset code blocks, table headers, inactive input containers, and canvas metadata trays.
- **Line (`#DEE1E6`):** Standard single-pixel borders, column dividers, and dependency connectors.
- **Inverse (`#22262D`):** Toast notifications, floating command bars, and inverted keyboard shortcut indicators.

### Status Indicators
- **Success / Unblocked (`#217B44`):** Ready dependencies, successful run-rate syncs, completed operational items.
- **Warning / Pending (`#AB6C00`):** Approaching deadlines, uncommitted drafts, soft dependency conflicts.
- **Danger / Blocked (`#BE423F`):** Critical upstream blocks, hard capacity collisions, destructive operational operations.

## Typography

The typographic hierarchy implements an information-dense schema optimized for fast scanning of nested hierarchies. 

### Font Roles
- **Inter:** Drives general UI composition, high-density table contents, form schemas, and structural headlines. Characterized by balanced vertical metrics and exceptional rendering legibility at small sizes (12px–13px).
- **JetBrains Mono:** Dedicated to computational metrics, ISO timestamps, issue/event identifier tags (e.g., `EVT-4091`), currency values, and keyboard shortcuts.

### Implementation Guidelines
- Restrict all micro-badges and column sorting labels to `label-caps` with uppercase transformation.
- For timeline Gantt bars, run times, and progress percentages, apply `label-code-sm` to maintain uniform tabular widths across changing numerical values.
- Maintain a strict 13px baseline for dense tabular data rows to optimize information density without sacrificing touch or pointer accuracy.

## Layout & Spacing

The layout model operates on an 8pt architectural grid with an internal 4pt subgrid for fine-grained component alignment.

### Layout Philosophy
- **Fluid Structural Canvas:** Main workspace views (Gantt, kanban, dependency matrix) expand to 100% of viewport width with a persistent, collapsible 240px utility sidebar and contextual inspector drawer (320px–400px).
- **Density Over Sprawl:** Internal component padding prioritizes vertical compactness (`space-xs` and `space-sm`) to ensure users can monitor complex critical paths without excessive vertical scrolling.
- **Breakpoints:**
  - `Mobile` (< 768px): Inspector drawers convert to bottom sheets; main navigation collapses into a unified command palette; sidebars tuck behind an overlay toggle.
  - `Tablet` (768px - 1024px): Split views stack into tabbed viewports; dependency graph transitions into linear list views.
  - `Desktop` (> 1024px): Full concurrent three-column orchestration (Navigation, Center Pipeline/Canvas, Right Inspector).

## Elevation & Depth

Visual hierarchy in this design system is driven by tonal containment, single-pixel hairline boundaries, and restrained ambient depth cues. Avoid blur-heavy glassmorphism or high-contrast drop shadows.

### Elevation Levels
- **Canvas Base (Level 0):** Background tone (`#FAFBFD`). Used for root views and main timeline tracks.
- **Card / Surface (Level 1):** Flat `#FFFFFF` bound by a 1px solid hairline (`#DEE1E6`). No shadow. Used for grid items, inline nodes, and structural table cells.
- **Elevated Interactive (Level 2):** Applied to dragged cards, hover-activated table rows, and popovers:
  - Border: 1px solid `#DEE1E6`
  - Shadow: `0 1px 3px rgba(30, 34, 41, 0.05), 0 4px 12px rgba(30, 34, 41, 0.03)`
- **Floating Overlays & Menus (Level 3):** Dropdown selects, quick-search toolbars, and date pickers:
  - Border: 1px solid `#DEE1E6`
  - Shadow: `0 4px 6px -1px rgba(30, 34, 41, 0.06), 0 10px 24px -2px rgba(30, 34, 41, 0.08)`
- **Command Palette & Modal Dialogs (Level 4):** Central focus overlays:
  - Border: 1px solid rgba(222, 225, 230, 0.8)
  - Shadow: `0 20px 35px -5px rgba(30, 34, 41, 0.12), 0 0 1px rgba(30, 34, 41, 0.1)`
- **Toasts & Temporary System Notices (Inverse Level):** Solid `#22262D` base with no external stroke:
  - Shadow: `0 10px 15px -3px rgba(0, 0, 0, 0.15)`

## Shapes

The design uses an intentional, structured radius tier (`roundedness: 2`) that maintains software precision without feeling harsh or industrial.

### Corner Radii
- **Micro Radius (4px - `rounded-sm`):** Micro-badges, inline code blocks, checkboxes, segmented control segments, and status pips.
- **Component Standard (8px - `rounded-md`):** Primary and secondary buttons, input fields, dropdown trigger buttons, tooltips, and timeline bars.
- **Container Radius (12px - `rounded-lg`):** Cards, flyout panels, canvas boards, modals, and dependency group wrappers.
- **Pill Radius (9999px - `rounded-full`):** User avatars, progress bars, and floating operational quick-counters.

## Components

### Buttons
- **Primary:** Filled `#5A5CE3`, text `#FFFFFF`, border none. Hover: `#4A4CC8`. Focus: 2px ring of `#5A5CE3` offset by 2px `#FAFBFD`. Active: `#3F41B3`.
- **Secondary:** Filled `#FFFFFF`, text `#2D3137`, 1px border `#DEE1E6`. Hover: background `#F4F5F8`.
- **Ghost / Soft:** Filled `#EFF1FF`, text `#5A5CE3`, border none. Hover: background `#DEE3FF`.
- **Compact Sizing:** Default height is 32px for workspace toolbars; 24px for micro-actions within table rows and dependency tracks.

### Micro-Badges & Dependency States
- **Format:** Upper-case, `label-caps` typography, 20px total height, horizontal padding `6px`, corner radius `4px`.
- **Ready / Unblocked:** `#217B44` background at 10% opacity, border 1px solid rgba(33, 123, 68, 0.2), text `#217B44`. Preceded by a 6px circular green pip.
- **Blocked / Locked:** `#BE423F` background at 10% opacity, border 1px solid rgba(190, 66, 63, 0.2), text `#BE423F`. Includes an inline padlock or stop icon.
- **Pending / Scheduled:** `#AB6C00` background at 10% opacity, border 1px solid rgba(171, 108, 0, 0.2), text `#AB6C00`.

### Form Fields & Inputs
- **Base Style:** Background `#FFFFFF`, 1px border `#DEE1E6`, text `#1E2229`, placeholder text `#62666D`.
- **Height:** 32px standard, 28px dense.
- **Focus State:** Border changes to `#5A5CE3` with a subtle outer hairline `0 0 0 1px #5A5CE3`. Inset panels use `#F4F5F8` background with an inset 1px divider.

### Cards & Grid Containers
- **Structural Integrity:** Always rendered with a `#FFFFFF` fill and a 1px border `#DEE1E6`. Dividers between card header, body, and action footer are explicit 1px hairlines without elevation shifts.
- **Active Node Selection:** 1px solid `#5A5CE3` border accompanied by an inner inset background wash of `#EFF1FF` (at 40% opacity).

### Dependency Link Connectors
- Vector-drawn cubic Bezier curves in canvas views:
  - Neutral / Unresolved: 1.5px solid `#DEE1E6`.
  - Active Selected Chain: 2px solid `#5A5CE3`.
  - Blocked Chain: 1.5px dashed `#BE423F`.