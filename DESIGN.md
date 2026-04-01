# Design System — Alfred

## Product Context
- **What this is:** A knowledge factory that helps ambitious thinkers ingest, decompose, connect, and capitalize on what they know
- **Who it's for:** Ambitious generalists — curious people across domains who read widely, think deeply, and want to connect dots across fields
- **Space/industry:** Personal knowledge management (PKM) — peers: Notion, Obsidian, Roam, Reflect, Capacities, Mem
- **Project type:** Web application (Next.js 16, React 19, shadcn/ui, Tailwind CSS 4)

## Aesthetic Direction
- **Direction:** Midnight Editorial — editorial warmth meets structured intelligence
- **Decoration level:** Intentional — subtle paper-like grain texture on surfaces, thin ruled lines as dividers, micro-grain on dark backgrounds
- **Mood:** A private library at midnight. Intellectual but warm. Authored, not optimized. Where serious thinking happens, not where productivity is performed.
- **Reference sites:** Researched Notion, Obsidian, Reflect, Capacities, Linear, Readwise, Granola, Arc — Alfred occupies the warm editorial space no PKM tool claims

## Typography

Three voices with clear roles: serif for authored content, sans for interface, mono for system data.

- **Display/Hero:** Source Serif 4 — classical transitional serif (Times New Roman lineage), authoritative for major headings (H1 page titles, hero text). Optical sizing enabled.
- **Body + UI + Labels + Nav:** DM Sans — clean geometric sans with higher x-height than Inter. Use `font-medium` (500) for labels, overlines, and navigation to create hierarchy through weight.
- **Data/Tables/Metadata:** Berkeley Mono — warm monospace with excellent tabular figures. For timestamps, connection counts, Bloom levels, metrics, and all system-layer information. Falls back to JetBrains Mono.
- **Code only:** Berkeley Mono / JetBrains Mono — strictly for code blocks and pre-formatted text
- **Loading:** Google Fonts CDN — `Source+Serif+4:ital,opsz,wght@0,8..60,200..900;1,8..60,200..900`, `DM+Sans:ital,opsz,wght@0,9..40,100..1000;1,9..40,100..1000`, `JetBrains+Mono:ital,wght@0,100..800;1,100..800`
- **Berkeley Mono:** Self-hosted or fallback to JetBrains Mono (Berkeley Mono requires license)

### Type Scale
| Level | Font | Size | Line Height | Weight | Usage |
|-------|------|------|-------------|--------|-------|
| Display | Source Serif 4 | 64px / 4rem | 1.1 | 400 | Landing page hero |
| H1 | Source Serif 4 | 42px / 2.625rem | 1.15 | 400 | Page titles |
| H2 | Source Serif 4 | 28px / 1.75rem | 1.2 | 400 | Section headers |
| H3 | DM Sans | 20px / 1.25rem | 1.3 | 500 | Subsection headers |
| Body | DM Sans | 16px / 1rem | 1.6 | 400 | Default reading text |
| Body Small | DM Sans | 14px / 0.875rem | 1.5 | 400 | Secondary text, helpers |
| Label | DM Sans | 12px / 0.75rem | 1.5 | 500 | Nav items, badge text (uppercase, 0.1em tracking) |
| Overline | DM Sans | 10px / 0.625rem | 1.5 | 500 | Section labels, categories (uppercase, 0.15em tracking) |
| System | Berkeley Mono | 10px / 0.625rem | 1.5 | 500 | Timestamps, metadata, shortcuts (uppercase, 0.12em tracking) |
| Data | Berkeley Mono | 14px / 0.875rem | 1.5 | 400 | Numeric data, tabular content (tabular-nums) |

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
| `--rule` | `rgba(15,14,13,0.08)` | `rgba(250,248,245,0.06)` | Ruled line dividers |

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

- **Approach:** Grid-disciplined with editorial content rhythm
- **Grid:** 12 columns, 32px gutter
- **Breakpoints:** sm(640px), md(768px), lg(1024px), xl(1280px), 2xl(1440px)
- **Max content width:** 1200px
- **App shell:** Sidebar (220px) + Main content + Optional right panel (380px)

### Knowledge Dashboard Layout
The primary view is a three-panel layout:
- **Left sidebar:** Navigation with Berkeley Mono section headers (uppercase, 9px, 0.15em tracking) and DM Sans nav items
- **Main content:** Knowledge cards list with search bar, sorted by recency or relevance
- **Right panel:** Connections view showing related zettels + knowledge metrics (zettel count, link count, retention percentage)

### Knowledge Metrics (Dashboard)
Display domain-level metrics in a data table within the dashboard view:
- Domains: System Design, AI Engineering, Finance, Philosophy, Geopolitics, etc.
- Metrics per domain: Zettel count, Connection count, Retention %, Bloom level
- Use Source Serif 4 for stat hero numbers, Berkeley Mono for tabular data

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
- **Ruled lines:** 1px solid using `--rule` token for section dividers within content
- **Card depth:** Subtle box shadows using warm-toned RGBA values, not cool grays

## Component Conventions

### Navigation
- Sidebar section headers in Berkeley Mono, 9px, font-medium, uppercase, 0.15em tracking
- Nav items in DM Sans, 13px, regular weight
- Active state: accent text + accent left border (2px) + accent-subtle background
- Hover: text-primary color + accent-subtle background

### Knowledge Cards
- Background: `--bg-card`
- Border: 1px solid `--border`
- Border-radius: `md` (8px)
- Hover: 2-3px accent top-border fade in + border-strong
- Title: Source Serif 4, 18-20px
- Body excerpt: DM Sans, 13-14px, text-secondary
- Footer: Berkeley Mono metadata (date, connection count, Bloom level) separated by ruled line
- Tags: DM Sans, 9px, font-medium, uppercase, accent-muted background

### Badges/Tags
- DM Sans, 10px, font-medium, uppercase, 0.05em tracking
- Dot indicator before text
- Semantic background tints (accent-muted, success/15%, warning/15%, error/15%)
- Border-radius: 2px (sharp, not rounded)

### Buttons
- Font: DM Sans, 13px, font-medium, 0.03em tracking
- Primary: accent background, light text
- Secondary: transparent, border, primary text
- Ghost: transparent, no border, secondary text
- Border-radius: `sm` (4px)

### Data Tables
- Header: Berkeley Mono, 10px, font-medium, uppercase, 0.1em tracking, tertiary color
- Body: DM Sans, 14px
- Numeric columns: Berkeley Mono, tabular-nums, 500 weight
- Row hover: accent-subtle background
- Dividers: ruled-line token

### Inputs
- Font: DM Sans, 14px
- Label: DM Sans, 11px, font-medium, uppercase, 0.05em tracking
- Border: 1px solid `--border-strong`
- Focus: border-color transitions to accent
- Border-radius: `sm` (4px)

### Alerts
- Left border: 3px solid semantic color
- Background: semantic color at 8% opacity
- Text: semantic color
- Font: DM Sans, 14px

### Search Bar
- Background: `--bg-secondary`
- Border: 1px solid `--border`
- Border-radius: `sm` (4px)
- Input: DM Sans, 13px
- Shortcut hint: Berkeley Mono, 9px, bordered pill

### Stats / Metrics
- Hero numbers: Source Serif 4, 28px, accent color
- Labels: Berkeley Mono, 9px, uppercase, 0.12em tracking, tertiary color

## Decisions Log
| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-03-21 | Initial design system created | Created by /design-consultation based on competitive research of Notion, Obsidian, Reflect, Capacities |
| 2026-03-21 | Serif display font (Instrument Serif) | No PKM tool uses serifs — instant differentiation, literary character |
| 2026-03-21 | Deep orange accent (#E8590C) instead of purple/blue | Every competitor uses purple or blue — terracotta/orange is warm, earthy, distinctive |
| 2026-03-21 | High-contrast duotone color approach | Monochrome + single accent means every orange element has maximum visual weight |
| 2026-03-21 | Grain texture on surfaces | Prevents flat/sterile feel, adds physical quality without skeuomorphism |
| 2026-03-21 | Warm grays (stone, not steel) | Reinforces intellectual warmth — cool grays would fight the serif + terracotta direction |
| 2026-03-29 | Inter (sans) for all UI, mono only for code | JetBrains Mono on every button/label/badge was too heavy and "terminal-like". Inter throughout with font-medium for labels creates hierarchy through weight, not font family. |
| 2026-04-01 | Typography overhaul: Source Serif 4 + DM Sans + Berkeley Mono | Three-voice system: classical serif for authored content (display), geometric sans for interface (body/UI), warm mono for system data (timestamps/metrics). Competitive research + outside voices (Codex, Claude) all converged on serif display + mono data layer. Source Serif 4 chosen for Times New Roman-like authority. |
| 2026-04-01 | Aesthetic shift: "Literary Terminal" to "Midnight Editorial" | Evolved from retro terminal energy to pure editorial. Less command-line, more independent journal. Warmth stays, terminal cosplay goes. |
| 2026-04-01 | Knowledge Dashboard as primary layout | Three-panel dashboard: sidebar nav + knowledge card list + connections panel + domain metrics table. Researched Linear, Notion, Capacities app shells. |
| 2026-04-01 | Berkeley Mono for all system-layer text | Timestamps, metadata, shortcuts, section headers in mono. Creates distinct "system voice" separate from content. Both outside design voices independently recommended this. |
| 2026-04-01 | Kept existing color palette (#E8590C, #0F0E0D) | Outside voices proposed tobacco amber (#C46A2B) but user preferred existing deep orange and warm charcoal. Proven distinctive in the space. |
