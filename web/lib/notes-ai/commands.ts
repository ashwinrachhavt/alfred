/**
 * Notes AI command registry.
 *
 * Single source of truth for the inline prompt's grouped flyout AND the
 * slash menu's `/ai...` family. Each command has a stable id, a Notion-style
 * label, and a `promptTemplate` that gets sent to streamWritingCompose.
 *
 * The inline prompt opens the flyout at the top level (Edit / Generate /
 * Draft / Ask), with submenus rendered for tone and translate variants.
 *
 * The slash menu emits each non-submenu command as its own `/ai-*` entry so
 * power users can hit "/ai improve" and skip the flyout.
 */

import {
  ArrowDown,
  ArrowUp,
  CheckCircle2,
  FileText,
  Globe,
  HelpCircle,
  Lightbulb,
  ListChecks,
  Mail,
  MessageSquare,
  Newspaper,
  NotebookPen,
  Pen,
  Search,
  Sparkles,
  Twitter,
  Wand2,
  type LucideIcon,
} from "lucide-react";

import { TONE_LABEL, TONE_VARIANTS, TRANSLATE_LABEL, TRANSLATE_VARIANTS } from "./followups";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type AICommandGroup = "edit" | "generate" | "draft" | "ask";

/**
 * What context the LLM needs in order to satisfy the command.
 *
 * - `selection`: requires a non-empty selection (Edit-on-selection commands).
 * - `paragraph`: uses the current paragraph (Edit-on-paragraph commands).
 * - `page`: uses the whole page as context (Generate / Draft / Ask).
 * - `none`: free-form, no context attached.
 */
export type AIContextMode = "selection" | "paragraph" | "page" | "none";

export type AICommand = {
  id: string;
  group: AICommandGroup;
  label: string;
  description?: string;
  icon: LucideIcon;
  /**
   * Free-form instruction sent to streamWritingCompose. May reference
   * `{selection}` / `{paragraph}` placeholders that the inline prompt
   * substitutes before submit.
   */
  promptTemplate: string;
  contextMode: AIContextMode;
  /**
   * Whether this command opens the side panel ("Ask Polymath") instead of
   * inline streaming. Side-panel commands flow through the agent SSE rather
   * than the writing endpoint.
   */
  panel?: boolean;
  /** If present, the slash menu surfaces this command as `/ai-{slashAlias}`. */
  slashAlias?: string;
};

// ---------------------------------------------------------------------------
// Edit commands (require selection or paragraph)
// ---------------------------------------------------------------------------

const EDIT_BASE: AICommand[] = [
  {
    id: "improve_writing",
    group: "edit",
    label: "Improve writing",
    description: "Tighten clarity, rhythm, and precision",
    icon: Wand2,
    promptTemplate:
      "Rewrite this passage to improve clarity, rhythm, and precision. Remove filler. Preserve meaning and voice. Output only the rewritten passage.",
    contextMode: "paragraph",
    slashAlias: "improve",
  },
  {
    id: "fix_grammar",
    group: "edit",
    label: "Fix spelling & grammar",
    description: "Correct mistakes without changing voice",
    icon: CheckCircle2,
    promptTemplate:
      "Fix spelling, grammar, and punctuation errors. Do not change wording, tone, or structure beyond what is required. Output only the corrected passage.",
    contextMode: "paragraph",
    slashAlias: "fix",
  },
  {
    id: "make_shorter",
    group: "edit",
    label: "Make shorter",
    description: "Condense without losing substance",
    icon: ArrowUp,
    promptTemplate:
      "Condense this passage. Keep every load-bearing claim; remove filler, hedges, and repetition. Output only the condensed passage.",
    contextMode: "paragraph",
    slashAlias: "shorter",
  },
  {
    id: "make_longer",
    group: "edit",
    label: "Make longer",
    description: "Expand with examples and stronger transitions",
    icon: ArrowDown,
    promptTemplate:
      "Expand this passage with sharper explanation, concrete examples, and stronger transitions. Preserve voice and core claims. Output only the expanded passage.",
    contextMode: "paragraph",
    slashAlias: "longer",
  },
  {
    id: "simplify",
    group: "edit",
    label: "Simplify language",
    description: "Plainer words, shorter sentences",
    icon: Sparkles,
    promptTemplate:
      "Simplify the language. Use shorter sentences and plainer words. Keep every claim. Output only the simplified passage.",
    contextMode: "paragraph",
    slashAlias: "simplify",
  },
];

const TONE_COMMANDS: AICommand[] = TONE_VARIANTS.map((variant) => ({
  id: `change_tone:${variant}`,
  group: "edit" as const,
  label: TONE_LABEL[variant],
  description: `Rewrite in a ${TONE_LABEL[variant].toLowerCase()} tone`,
  icon: MessageSquare,
  promptTemplate: `Rewrite this passage in a ${TONE_LABEL[variant].toLowerCase()} tone. Preserve all factual content. Output only the rewritten passage.`,
  contextMode: "paragraph" as const,
}));

const TRANSLATE_COMMANDS: AICommand[] = TRANSLATE_VARIANTS.map((variant) => ({
  id: `translate:${variant}`,
  group: "edit" as const,
  label: TRANSLATE_LABEL[variant],
  description: `Translate into ${TRANSLATE_LABEL[variant]}`,
  icon: Globe,
  promptTemplate: `Translate this passage into ${TRANSLATE_LABEL[variant]}. Preserve markdown structure exactly. Output only the translation.`,
  contextMode: "paragraph" as const,
}));

// ---------------------------------------------------------------------------
// Generate commands (insert at cursor with page context)
// ---------------------------------------------------------------------------

const GENERATE_COMMANDS: AICommand[] = [
  {
    id: "continue_writing",
    group: "generate",
    label: "Continue writing",
    description: "Pick up where the cursor is",
    icon: Pen,
    promptTemplate:
      "Continue this note naturally from where the cursor is. Match the existing voice, level of detail, and structure. Do not repeat or summarize.",
    contextMode: "page",
    slashAlias: "continue",
  },
  {
    id: "summarize_page",
    group: "generate",
    label: "Summarize page",
    description: "Tight summary of the whole note",
    icon: FileText,
    promptTemplate:
      "Summarize this entire note. Lead with the single most important takeaway, then a tight bulleted list of supporting points. Output only the summary.",
    contextMode: "page",
    slashAlias: "summarize",
  },
  {
    id: "find_action_items",
    group: "generate",
    label: "Find action items",
    description: "Extract a verb-led checklist",
    icon: ListChecks,
    promptTemplate:
      "Extract action items from this note. Output a markdown checklist with each item phrased as a verb-led task. If there are none, output exactly: \"No action items found.\"",
    contextMode: "page",
    slashAlias: "actions",
  },
  {
    id: "explain_selection",
    group: "generate",
    label: "Explain this",
    description: "Clarify a selected passage",
    icon: HelpCircle,
    promptTemplate:
      "Explain this passage as if to a smart non-expert. Define unfamiliar terms inline. Preserve technical substance. Output only the explanation.",
    contextMode: "selection",
    slashAlias: "explain",
  },
];

// ---------------------------------------------------------------------------
// Draft commands (generate from scratch)
// ---------------------------------------------------------------------------

const DRAFT_COMMANDS: AICommand[] = [
  {
    id: "draft_brainstorm",
    group: "draft",
    label: "Brainstorm ideas",
    description: "Generate a list of starting points",
    icon: Lightbulb,
    promptTemplate:
      "Brainstorm a list of 7 ideas. Output a markdown bulleted list. Each item is one sentence. No preamble.",
    contextMode: "none",
    slashAlias: "brainstorm",
  },
  {
    id: "draft_outline",
    group: "draft",
    label: "Outline",
    description: "Compact section outline",
    icon: NotebookPen,
    promptTemplate:
      "Create a compact markdown outline using H2 and H3 headings. No prose under headings. No preamble.",
    contextMode: "none",
    slashAlias: "outline",
  },
  {
    id: "draft_blog_post",
    group: "draft",
    label: "Blog post",
    description: "Editorial draft with structure",
    icon: Newspaper,
    promptTemplate:
      "Draft a blog post with a clear thesis, 3-4 sections under H2 headings, and a short closing thought. Use markdown. No preamble.",
    contextMode: "none",
    slashAlias: "blog",
  },
  {
    id: "draft_social_post",
    group: "draft",
    label: "Social post",
    description: "Punchy short-form post",
    icon: Twitter,
    promptTemplate:
      "Draft a punchy short-form social post. Lead with a strong hook. Avoid hashtags unless requested. Output only the post text.",
    contextMode: "none",
    slashAlias: "social",
  },
  {
    id: "draft_email",
    group: "draft",
    label: "Email",
    description: "Professional, concise message",
    icon: Mail,
    promptTemplate:
      "Draft a professional email. Concise, polite, with a clear ask. Output only the email body — no subject, no signature.",
    contextMode: "none",
    slashAlias: "email",
  },
];

// ---------------------------------------------------------------------------
// Ask commands (open side panel)
// ---------------------------------------------------------------------------

const ASK_COMMANDS: AICommand[] = [
  {
    id: "ask_polymath",
    group: "ask",
    label: "Ask Polymath",
    description: "Chat with the agent in the side panel",
    icon: MessageSquare,
    promptTemplate: "",
    contextMode: "none",
    panel: true,
  },
  {
    id: "research_topic",
    group: "ask",
    label: "Research this topic",
    description: "Search your knowledge base",
    icon: Search,
    promptTemplate: "Research this topic in my knowledge base.",
    contextMode: "selection",
    panel: true,
  },
];

// ---------------------------------------------------------------------------
// Registry
// ---------------------------------------------------------------------------

export const AI_COMMANDS: AICommand[] = [
  ...EDIT_BASE,
  ...TONE_COMMANDS,
  ...TRANSLATE_COMMANDS,
  ...GENERATE_COMMANDS,
  ...DRAFT_COMMANDS,
  ...ASK_COMMANDS,
];

const AI_COMMANDS_BY_ID = new Map<string, AICommand>(
  AI_COMMANDS.map((command) => [command.id, command]),
);

// ---------------------------------------------------------------------------
// Lookup helpers
// ---------------------------------------------------------------------------

export function getAICommand(id: string): AICommand | undefined {
  return AI_COMMANDS_BY_ID.get(id);
}

export function aiCommandsByGroup(): Record<AICommandGroup, AICommand[]> {
  const groups: Record<AICommandGroup, AICommand[]> = {
    edit: [],
    generate: [],
    draft: [],
    ask: [],
  };
  for (const command of AI_COMMANDS) {
    groups[command.group].push(command);
  }
  return groups;
}

/** Commands that should appear in the slash menu's `/ai-*` family. */
export function slashAICommands(): AICommand[] {
  return AI_COMMANDS.filter((command) => Boolean(command.slashAlias));
}

/** Edit-group commands grouped by the inline prompt's submenu structure. */
export function editSubmenu(): {
  base: AICommand[];
  tone: AICommand[];
  translate: AICommand[];
} {
  return {
    base: EDIT_BASE,
    tone: TONE_COMMANDS,
    translate: TRANSLATE_COMMANDS,
  };
}

/**
 * Substitute `{selection}` / `{paragraph}` placeholders in a prompt.
 *
 * The current set of templates do not contain placeholders (we let the
 * existing `selection` / `pageText` payload fields do the work) — this
 * helper is kept for forward-compat with future user-defined commands.
 */
export function fillPromptTemplate(
  template: string,
  values: { selection?: string; paragraph?: string },
): string {
  return template
    .replace(/\{selection\}/g, values.selection ?? "")
    .replace(/\{paragraph\}/g, values.paragraph ?? "");
}
