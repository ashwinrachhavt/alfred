# Alfred Frontend Design System (Bible)

This document is the **source of truth** for Alfred’s UI foundations and component usage. It’s intentionally practical: it tells you **what to use**, **when**, and **where it lives in code**.

## Goals

- **Clarity over cleverness**: predictable UI beats bespoke UI.
- **Semantic tokens first**: prefer tokens like `--background` over hard-coded colors.
- **Composable primitives**: small, accessible building blocks that scale to product UI.
- **Consistency**: spacing, typography, borders, and motion should feel like one system.

## Where things live

- **Tokens & base styles**: `frontend/app/globals.css`
- **UI primitives (shadcn-style, Radix-based)**: `frontend/components/ui/*`
- **Feature UI**: `frontend/features/*`
- **Reusable layout primitives**: `frontend/components/layout/*`
- **Classname utility**: `frontend/lib/utils.ts` (`cn`)
- **In-app showcase**: `frontend/app/(app)/design-system/page.tsx`

## Foundations

### Color system

We use **semantic color tokens** (CSS variables), defined for both light and dark:

- Light: `:root` in `frontend/app/globals.css`
- Dark: `.dark` in `frontend/app/globals.css`

Core semantic tokens:

- Surfaces: `--background`, `--card`, `--popover`, `--sidebar`
- Text: `--foreground`, `--muted-foreground`, `--card-foreground`
- Actions: `--primary`, `--primary-foreground`, `--secondary`, `--accent`, `--destructive`
- Borders & focus: `--border`, `--input`, `--ring`

Implementation detail:

- Tailwind v4 maps semantic variables to utilities via `@theme inline` (see the `--color-*` declarations in `frontend/app/globals.css`).
- Prefer utilities like `bg-background`, `text-foreground`, `border-border` rather than raw color values.

Adding/adjusting a token:

1. Update `:root` and `.dark` values in `frontend/app/globals.css` (use **OKLCH** like the rest of the file).
2. If it should be a Tailwind utility, ensure it’s mapped in `@theme inline`.
3. Use it in components by referencing the semantic utility (e.g. `bg-card`).

### Typography

- Font families are configured in `frontend/app/layout.tsx` via `next/font` (Geist + Geist Mono).
- Tailwind uses `font-sans` / `font-mono` mapped in `frontend/app/globals.css` (`--font-sans`, `--font-mono`).

Guidelines:

- Use **one** primary scale for headings: `text-lg` → `text-4xl` with `font-semibold` and `tracking-tight` for titles.
- Body copy: `text-sm` / `text-base` with `text-muted-foreground` for secondary text.
- Avoid custom font sizes unless you’re introducing a new system-level pattern.

### Spacing & layout

We rely on Tailwind spacing utilities.

Guidelines:

- Prefer `space-y-*`/`gap-*` over manual margins.
- Favor layouts that work at small widths first; use `md:`/`lg:` for progressive enhancement.
- Use `Page` from `frontend/components/layout/page` for consistent page paddings and widths.

### Radius

Radius is tokenized:

- Base token: `--radius` in `frontend/app/globals.css`
- Derived: `--radius-sm`, `--radius-md`, `--radius-lg`, …

Guidelines:

- Component defaults should use the system radius (e.g. `rounded-lg`, `rounded-3xl` only for intentional “hero” surfaces).

### Motion

Guidelines:

- Keep animations subtle and fast (150–250ms).
- Always preserve usability: respect reduced motion where possible, and never animate layout in a way that breaks focus/keyboard flows.

## Components

### General rules

- Prefer existing primitives in `frontend/components/ui/*` before creating a new component.
- Variants should use `class-variance-authority` (CVA), as in `frontend/components/ui/button.tsx`.
- **Accessibility is non-negotiable**:
  - Use Radix primitives for dialogs/menus/tabs when possible.
  - Ensure keyboard navigation works.
  - Ensure focus rings are visible (`focus-visible:*` patterns are standardized in primitives).

### Buttons

Use `Button` from `frontend/components/ui/button.tsx`.

- `variant`: `default | secondary | outline | ghost | link | destructive`
- `size`: `default | sm | lg | icon | icon-sm | icon-lg`

Guidelines:

- Use `default` for primary actions, `secondary/outline` for secondary actions.
- Use `destructive` only when the action is irreversible or dangerous.
- Prefer `asChild` to wrap links without losing semantics.

### Forms

Use `Label`, `Input`, and higher-level patterns like `InputGroup` where appropriate:

- `frontend/components/ui/label.tsx`
- `frontend/components/ui/input.tsx`
- `frontend/components/ui/input-group.tsx`

Guidelines:

- Always pair inputs with labels (visually or via `aria-label` when needed).
- Show validation using existing `aria-invalid` styles already present in primitives.

### Cards, dialogs, navigation

Prefer these primitives:

- `Card`: `frontend/components/ui/card.tsx`
- `Dialog`: `frontend/components/ui/dialog.tsx`
- `Tabs`: `frontend/components/ui/tabs.tsx`
- Sidebar primitives: `frontend/components/ui/sidebar.tsx`

Guidelines:

- Cards are for grouping related content; don’t over-card everything.
- Dialogs are for short, focused tasks (confirmation, small forms). Avoid turning dialogs into full pages.

### Feedback (toasts, empty states, loading)

- Toasts: `sonner` (see usage patterns in the codebase; keep copy short and action-oriented).
- Empty states: `frontend/components/ui/empty-state.tsx`

Guidelines:

- Empty states should answer: “What is this?”, “Why is it empty?”, “What can I do next?”

## Patterns

### Page structure

- Use `Page` (`frontend/components/layout/page`) to enforce consistent widths and padding.
- Default to a clear page title + description, then content blocks.

### Content hierarchy

- One primary action per view; secondary actions visually subordinate.
- Use muted text (`text-muted-foreground`) for guidance and descriptions.

## Theming

- Theme switching uses `next-themes` via `frontend/components/theme-provider.tsx`.
- Theme is applied by toggling `.dark` at the document level.

Guidelines:

- Do not introduce per-component theme toggles.
- All colors should be derived from semantic tokens so light/dark remains consistent.

## Contribution checklist

Before merging UI work:

- Uses semantic tokens (`bg-background`, `text-foreground`, etc.)
- Reuses primitives where possible (`frontend/components/ui/*`)
- Keyboard navigation works (Tab/Shift+Tab, Enter/Space where relevant)
- Focus rings are visible
- Copy is short and specific
- Layout holds up on small screens

