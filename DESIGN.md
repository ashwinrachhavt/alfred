# Design System — Alfred

## Product Context
- **What this is:** A knowledge factory that helps ambitious thinkers ingest, decompose, connect, and capitalize on what they know
- **Who it's for:** Ambitious generalists — curious people across domains who read widely, think deeply, and want to connect dots across fields
- **Space/industry:** Personal knowledge management (PKM) — peers: Notion, Obsidian, Roam, Reflect, Capacities, Mem
- **Project type:** Web application (Next.js 16, React 19, shadcn/ui, Tailwind CSS 4)

## Aesthetic Direction
- **Direction:** Editorial/Industrial Hybrid — "Literary Terminal"
- **Decoration level:** Intentional — subtle paper-like grain texture on surfaces, thin ruled lines as dividers, micro-grain on dark backgrounds
- **Mood:** A designer's workshop meets a library reading room. Intellectual but warm. Sophisticated but not intimidating. A place where serious thinking happens.
- **Reference sites:** Researched Notion, Obsidian, Reflect, Capacities — Alfred deliberately breaks from the PKM convention of purple/violet gradients and geometric sans-serifs

## Typography

Three typographic voices create hierarchy without relying on color:

- **Display/Hero:** Instrument Serif — literary character, no PKM tool uses serifs. Says "intellectual, authoritative" instead of "tech startup"
- **Body:** DM Sans — clean humanist sans with personality, excellent readability at all sizes
- **UI/Labels/Nav/Metadata:** JetBrains Mono — creates a "system layer" that feels machine-like and precise. Used for navigation items, timestamps, counts, tags, section overlines, and all metadata
- **Data/Tables:** Geist (tabular-nums) — already in the project, excellent for numeric data alignment
- **Code:** JetBrains Mono
- **Loading:** Google Fonts CDN — `Instrument+Serif:ital@0;1`, `DM+Sans:ital,opsz,wght@0,9..40,100..1000;1,9..40,100..1000`, `JetBrains+Mono:ital,wght@0,100..800;1,100..800`, `Geist:wght@100..900`

### Type Scale
| Level | Font | Size | Line Height | Weight | Usage |
|-------|------|------|-------------|--------|-------|
| Display | Instrument Serif | 64px / 4rem | 1.1 | 400 | Landing page hero |
| H1 | Instrument Serif | 42px / 2.625rem | 1.15 | 400 | Page titles |
| H2 | Instrument Serif | 28px / 1.75rem | 1.2 | 400 | Section headers |
| H3 | DM Sans | 20px / 1.25rem | 1.3 | 500 | Subsection headers |
| Body | DM Sans | 16px / 1rem | 1.6 | 400 | Default reading text |
| Body Small | DM Sans | 14px / 0.875rem | 1.5 | 400 | Secondary text, helpers |
| Label | JetBrains Mono | 12px / 0.75rem | 1.5 | 400 | Nav items, metadata, timestamps |
| Overline | JetBrains Mono | 10px / 0.625rem | 1.5 | 500 | Section labels, categories (uppercase, 0.1em tracking) |

## Color

- **Approach:** High-contrast duotone — almost everything is warm monochrome with a single deep orange accent. When something is orange, it matters.

### Core Palette
| Token | Light | Dark | Usage |
|-------|-------|------|-------|
| `--bg-primary` | `#FAF8F5` | `#0F0E0D` | Page background |
| `--bg-secondary` | `#F0EDE8` | `#1A1918` | Surface / card background |
| `--bg-tertiary` | `#E8E4DF` | `#252321` | Elevated surface |
| `--bg-card` | `#FFFFFF` | `#1A1918` | Card background |
| `--text-primary` | `#0F0E0D` | `#FAF8F5` | Primary text |
| `--text-secondary` | `#5C5650` | `#A39E97` | Secondary text |
| `--text-tertiary` | `#8A837B` | `#6B665F` | Tertiary text, placeholders |
| `--accent` | `#E8590C` | `#E8590C` | Primary accent — CTA, active states, highlights |
| `--accent-hover` | `#D14E08` | `#F06B20` | Accent hover state |
| `--accent-subtle` | `rgba(232,89,12,0.08)` | `rgba(232,89,12,0.1)` | Accent background tint |
| `--accent-muted` | `rgba(232,89,12,0.15)` | `rgba(232,89,12,0.2)` | Badge/tag background |
| `--border` | `rgba(15,14,13,0.1)` | `rgba(250,248,245,0.08)` | Default border |
| `--border-strong` | `rgba(15,14,13,0.2)` | `rgba(250,248,245,0.15)` | Emphasized border |

### Semantic Colors
| Token | Value | Usage |
|-------|-------|-------|
| `--success` | `#2D6A4F` | Connected, synced, positive |
| `--warning` | `#B45309` | Needs review, approaching due |
| `--error` | `#C2410C` | Failed, expired, overdue |
| `--info` | `#1D4ED8` | Informational, links |

### Dark Mode Strategy
- Default theme is dark (`#0F0E0D` base)
- Warm charcoal surfaces, NOT cool blue-blacks
- Accent stays the same hue, hover state lightens slightly
- Reduce saturation ~10% on semantic colors
- Grain texture at 3.5% opacity (vs 3% light mode)

## Spacing

- **Base unit:** 8px
- **Density:** Comfortable — generous in reading views, tighter in navigation and metadata

### Scale
| Token | Value | Usage |
|-------|-------|-------|
| `2xs` | 4px | Inline gaps, icon-to-text |
| `xs` | 8px | Tight element spacing |
| `sm` | 16px | Default element gap |
| `md` | 24px | Section internal padding |
| `lg` | 32px | Content area padding |
| `xl` | 48px | Section separation |
| `2xl` | 64px | Major section gaps |
| `3xl` | 96px | Page-level spacing |

## Layout

- **Approach:** Grid-disciplined with editorial content areas
- **Grid:** 12 columns, 32px gutter
- **Breakpoints:** sm(640px), md(768px), lg(1024px), xl(1280px), 2xl(1440px)
- **Max content width:** 1200px
- **App shell:** Sidebar (220px) + Main content + Optional right panel (360px)

### Border Radius
| Token | Value | Usage |
|-------|-------|-------|
| `sm` | 4px | Buttons, inputs, badges |
| `md` | 8px | Cards, dropdowns |
| `lg` | 12px | Modals, app shell panels |
| `full` | 9999px | Avatars, pills |

## Motion

- **Approach:** Intentional — smooth transitions that aid comprehension, spring physics for drag-and-drop
- **No gratuitous animation** — every motion must serve a purpose (feedback, spatial awareness, or state change)

### Timing
| Token | Duration | Easing | Usage |
|-------|----------|--------|-------|
| `micro` | 50-100ms | ease-out | Hover states, toggles, color changes |
| `short` | 150-250ms | ease-out | Panel open/close, element entrance |
| `medium` | 250-400ms | ease-in-out | Page transitions, complex state changes |
| `spring` | 300-400ms | cubic-bezier(0.34, 1.56, 0.64, 1) | Drag-and-drop, canvas interactions |

### Easing
- **Enter:** ease-out (elements arriving)
- **Exit:** ease-in (elements leaving)
- **Move:** ease-in-out (elements repositioning)
- **Spring:** cubic-bezier(0.34, 1.56, 0.64, 1) (playful, physical interactions)

## Texture

- **Grain overlay:** SVG noise filter at 3% opacity (light) / 3.5% (dark), `position: fixed`, `pointer-events: none`
- **Ruled lines:** 1px solid using `--ruled-line` token for section dividers within content
- **Card depth:** Subtle box shadows using warm-toned RGBA values, not cool grays

## Component Conventions

### Navigation
- Sidebar labels in JetBrains Mono, 12px, uppercase
- Active state: orange text + orange left border + accent-subtle background
- Section headers: JetBrains Mono, 9px, uppercase, 0.15em tracking

### Badges/Tags
- JetBrains Mono, 10px, uppercase
- Dot indicator before text
- Semantic background tints (accent-muted, success/15%, warning/15%, error/15%)
- Border-radius: 2px (sharp, not rounded)

### Cards
- Background: `--bg-card`
- Border: 1px solid `--border`
- Border-radius: `md` (8px)
- Hover: 3px accent top-border fade in
- Content: Serif title + Sans body + Mono metadata footer separated by ruled line

### Buttons
- Font: JetBrains Mono, 13px, 0.03em tracking
- Primary: accent background, light text
- Secondary: transparent, border, primary text
- Ghost: transparent, no border, secondary text
- Border-radius: `sm` (4px)

### Data Tables
- Header: JetBrains Mono, 10px, uppercase, 0.1em tracking, tertiary color
- Body: DM Sans, 14px
- Numeric columns: Geist, tabular-nums, 500 weight
- Row hover: accent-subtle background
- Dividers: ruled-line token

### Inputs
- Font: DM Sans, 14px
- Label: JetBrains Mono, 11px, 0.05em tracking
- Border: 1px solid `--border-strong`
- Focus: border-color transitions to accent
- Border-radius: `sm` (4px)

### Alerts
- Left border: 3px solid semantic color
- Background: semantic color at 8% opacity
- Text: semantic color
- Font: DM Sans, 14px

## Decisions Log
| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-03-21 | Initial design system created | Created by /design-consultation based on competitive research of Notion, Obsidian, Reflect, Capacities |
| 2026-03-21 | Serif display font (Instrument Serif) | No PKM tool uses serifs — instant differentiation, literary character |
| 2026-03-21 | Deep orange accent (#E8590C) instead of purple/blue | Every competitor uses purple or blue — terracotta/orange is warm, earthy, distinctive |
| 2026-03-21 | JetBrains Mono for all UI chrome | Creates "system layer" distinct from content — labels, nav, metadata all feel machine-like |
| 2026-03-21 | High-contrast duotone color approach | Monochrome + single accent means every orange element has maximum visual weight |
| 2026-03-21 | Grain texture on surfaces | Prevents flat/sterile feel, adds physical quality without skeuomorphism |
| 2026-03-21 | Warm grays (stone, not steel) | Reinforces intellectual warmth — cool grays would fight the serif + terracotta direction |
