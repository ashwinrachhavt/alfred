/**
 * Notes AI follow-up registry.
 *
 * Each follow-up is a *typed instruction template* rather than a free-form
 * re-prompt. That's what makes Notion's "Make longer" / "Continue writing" /
 * "Change tone" feel reliable instead of hallucinatory: the LLM gets a
 * specific instruction shape with the prior output as input, not a
 * conversational follow-up.
 *
 * The streaming controller resolves a follow-up id, deletes the prior AI
 * range, and re-enters streaming with the resolved instruction. The
 * pre-stream original range is preserved so accept still replaces it
 * correctly across multiple chained follow-ups.
 */

import {
  ArrowDown,
  ArrowUp,
  CheckCircle2,
  FileText,
  Globe,
  HelpCircle,
  ListChecks,
  MessageSquare,
  Pen,
  RefreshCcw,
  Sparkles,
  Wand2,
  type LucideIcon,
} from "lucide-react";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type ToneVariant = "professional" | "casual" | "direct" | "confident" | "friendly";
export type TranslateVariant = "en" | "es" | "fr" | "de" | "ja" | "zh";

export type FollowupId =
  | "try_again"
  | "continue_writing"
  | "make_longer"
  | "make_shorter"
  | "improve_writing"
  | "fix_grammar"
  | "summarize"
  | "explain"
  | "simplify"
  | "find_action_items"
  | `change_tone:${ToneVariant}`
  | `translate:${TranslateVariant}`;

/**
 * What kind of work the follow-up performs on the prior AI output.
 *
 * - `rewrite`: produce a new version that *replaces* the prior output.
 *   Most follow-ups are rewrites.
 * - `extend`: produce text that should be *appended* after the prior
 *   output. `continue_writing` is the only extend follow-up.
 * - `transform`: produce a structurally-different artifact derived from
 *   the prior output (e.g., summary, action-item list, explanation).
 */
export type FollowupMode = "rewrite" | "extend" | "transform";

export type FollowupGroup = "primary" | "tone" | "translate" | "transform";

export type FollowupContext = {
  prevOutput: string;
  originalSelection: string | null;
  pageTitle: string;
};

export type FollowupDef = {
  id: FollowupId;
  label: string;
  group: FollowupGroup;
  icon: LucideIcon;
  mode: FollowupMode;
  /** Single-letter keyboard shortcut when no input has focus. */
  shortcut?: string;
  instructionTemplate: (ctx: FollowupContext) => string;
};

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const TONE_LABELS: Record<ToneVariant, string> = {
  professional: "Professional",
  casual: "Casual",
  direct: "Direct",
  confident: "Confident",
  friendly: "Friendly",
};

const TONE_DESCRIPTIONS: Record<ToneVariant, string> = {
  professional: "even-keeled, polished, free of slang or hedges",
  casual: "warm, conversational, lightly informal — but not slack",
  direct: "blunt and load-bearing — every sentence carries weight",
  confident: "assertive and assured, without overclaiming",
  friendly: "warm and approachable while staying professional",
};

const TRANSLATE_LABELS: Record<TranslateVariant, string> = {
  en: "English",
  es: "Spanish",
  fr: "French",
  de: "German",
  ja: "Japanese",
  zh: "Mandarin Chinese",
};

/**
 * Wrap the prior output as a fenced "Passage" block. We use plain delimiters
 * rather than markdown fences because the LLM might already be emitting
 * markdown and we don't want to confuse the parser.
 */
function passageBlock(prev: string): string {
  return `Passage:\n---\n${prev}\n---`;
}

// ---------------------------------------------------------------------------
// Templates
// ---------------------------------------------------------------------------

function tryAgainTemplate(ctx: FollowupContext): string {
  // "Try again" intentionally does NOT include prior output — it asks for a
  // fresh attempt at the original task, given the same selection context.
  if (ctx.originalSelection) {
    return `Try a different approach to the original request. Original selection:\n---\n${ctx.originalSelection}\n---\n\nProduce a fresh attempt that differs from any prior generation. Output only the new version.`;
  }
  return "Try a different approach to the original request. Produce a fresh attempt that differs from any prior generation. Output only the new version.";
}

function continueWritingTemplate(ctx: FollowupContext): string {
  return `Continue this passage naturally from where it ends. Match the existing voice, level of detail, and structure. Do not repeat or summarize what is already written. Do not introduce new headings unless the passage was leading into one.\n\nExisting passage:\n---\n${ctx.prevOutput}\n---\n\nOutput only the continuation — do not echo the existing passage.`;
}

function makeLongerTemplate(ctx: FollowupContext): string {
  return `Expand the following passage with sharper explanation, concrete examples, and stronger transitions. Preserve voice and core claims. Do not summarize or restate. Output only the expanded passage.\n\n${passageBlock(ctx.prevOutput)}`;
}

function makeShorterTemplate(ctx: FollowupContext): string {
  return `Condense the following passage. Keep every load-bearing claim; remove filler, hedges, and repetition. Preserve the original structure (headings, lists) where they aid scanning. Output only the condensed passage.\n\n${passageBlock(ctx.prevOutput)}`;
}

function improveWritingTemplate(ctx: FollowupContext): string {
  return `Rewrite the following passage to improve clarity, rhythm, and precision. Remove filler and weak verbs. Keep the original meaning and voice. Output only the rewritten passage.\n\n${passageBlock(ctx.prevOutput)}`;
}

function fixGrammarTemplate(ctx: FollowupContext): string {
  return `Fix spelling, grammar, and punctuation errors in the following passage. Do not change wording, tone, or structure beyond what is required for correctness. Output only the corrected passage.\n\n${passageBlock(ctx.prevOutput)}`;
}

function summarizeTemplate(ctx: FollowupContext): string {
  return `Summarize the following passage. Lead with the single most important takeaway, then a tight bulleted list of supporting points. Keep it scannable. Output only the summary.\n\n${passageBlock(ctx.prevOutput)}`;
}

function explainTemplate(ctx: FollowupContext): string {
  return `Explain the following passage as if to a smart non-expert. Define unfamiliar terms inline. Preserve the technical substance. Output only the explanation.\n\n${passageBlock(ctx.prevOutput)}`;
}

function simplifyTemplate(ctx: FollowupContext): string {
  return `Simplify the language in the following passage. Use shorter sentences and plainer words. Keep every claim — do not delete content. Output only the simplified passage.\n\n${passageBlock(ctx.prevOutput)}`;
}

function findActionItemsTemplate(ctx: FollowupContext): string {
  return `Extract action items from the following passage. Output a markdown checklist with each item phrased as a verb-led task. If the passage has no action items, output exactly: "No action items found."\n\n${passageBlock(ctx.prevOutput)}`;
}

function changeToneTemplate(variant: ToneVariant) {
  return (ctx: FollowupContext): string =>
    `Rewrite the following passage in a ${TONE_LABELS[variant].toLowerCase()} tone (${TONE_DESCRIPTIONS[variant]}). Preserve all factual content and structure. Output only the rewritten passage.\n\n${passageBlock(ctx.prevOutput)}`;
}

function translateTemplate(variant: TranslateVariant) {
  return (ctx: FollowupContext): string =>
    `Translate the following passage into ${TRANSLATE_LABELS[variant]}. Preserve markdown structure (headings, lists, emphasis) exactly. Do not transliterate proper nouns unless idiomatic in the target language. Output only the translation.\n\n${passageBlock(ctx.prevOutput)}`;
}

// ---------------------------------------------------------------------------
// Registry
// ---------------------------------------------------------------------------

const TONE_FOLLOWUPS: FollowupDef[] = (Object.keys(TONE_LABELS) as ToneVariant[]).map((variant) => ({
  id: `change_tone:${variant}` as const,
  label: TONE_LABELS[variant],
  group: "tone",
  icon: MessageSquare,
  mode: "rewrite",
  instructionTemplate: changeToneTemplate(variant),
}));

const TRANSLATE_FOLLOWUPS: FollowupDef[] = (
  Object.keys(TRANSLATE_LABELS) as TranslateVariant[]
).map((variant) => ({
  id: `translate:${variant}` as const,
  label: TRANSLATE_LABELS[variant],
  group: "translate",
  icon: Globe,
  mode: "rewrite",
  instructionTemplate: translateTemplate(variant),
}));

export const FOLLOWUPS: FollowupDef[] = [
  {
    id: "try_again",
    label: "Try again",
    group: "primary",
    icon: RefreshCcw,
    mode: "rewrite",
    shortcut: "r",
    instructionTemplate: tryAgainTemplate,
  },
  {
    id: "continue_writing",
    label: "Continue writing",
    group: "primary",
    icon: Pen,
    mode: "extend",
    shortcut: "c",
    instructionTemplate: continueWritingTemplate,
  },
  {
    id: "make_longer",
    label: "Make longer",
    group: "primary",
    icon: ArrowDown,
    mode: "rewrite",
    shortcut: "l",
    instructionTemplate: makeLongerTemplate,
  },
  {
    id: "make_shorter",
    label: "Make shorter",
    group: "primary",
    icon: ArrowUp,
    mode: "rewrite",
    shortcut: "s",
    instructionTemplate: makeShorterTemplate,
  },
  {
    id: "improve_writing",
    label: "Improve writing",
    group: "primary",
    icon: Wand2,
    mode: "rewrite",
    instructionTemplate: improveWritingTemplate,
  },
  {
    id: "fix_grammar",
    label: "Fix spelling & grammar",
    group: "primary",
    icon: CheckCircle2,
    mode: "rewrite",
    instructionTemplate: fixGrammarTemplate,
  },
  {
    id: "summarize",
    label: "Summarize",
    group: "transform",
    icon: FileText,
    mode: "transform",
    instructionTemplate: summarizeTemplate,
  },
  {
    id: "explain",
    label: "Explain",
    group: "transform",
    icon: HelpCircle,
    mode: "transform",
    instructionTemplate: explainTemplate,
  },
  {
    id: "simplify",
    label: "Simplify language",
    group: "transform",
    icon: Sparkles,
    mode: "rewrite",
    instructionTemplate: simplifyTemplate,
  },
  {
    id: "find_action_items",
    label: "Find action items",
    group: "transform",
    icon: ListChecks,
    mode: "transform",
    instructionTemplate: findActionItemsTemplate,
  },
  ...TONE_FOLLOWUPS,
  ...TRANSLATE_FOLLOWUPS,
];

const FOLLOWUPS_BY_ID = new Map<FollowupId, FollowupDef>(
  FOLLOWUPS.map((followup) => [followup.id, followup]),
);

// ---------------------------------------------------------------------------
// Lookup helpers
// ---------------------------------------------------------------------------

export function getFollowup(id: FollowupId): FollowupDef | undefined {
  return FOLLOWUPS_BY_ID.get(id);
}

export function resolveFollowup(id: FollowupId, ctx: FollowupContext): string {
  const def = getFollowup(id);
  if (!def) throw new Error(`Unknown follow-up: ${id}`);
  return def.instructionTemplate(ctx);
}

export function followupsByGroup(): Record<FollowupGroup, FollowupDef[]> {
  const groups: Record<FollowupGroup, FollowupDef[]> = {
    primary: [],
    tone: [],
    translate: [],
    transform: [],
  };
  for (const followup of FOLLOWUPS) {
    groups[followup.group].push(followup);
  }
  return groups;
}

/** Returns the subset of follow-ups intended for the action bar's primary chip row. */
export function primaryFollowups(): FollowupDef[] {
  return FOLLOWUPS.filter((f) => f.group === "primary");
}

/** Tone variants for the "Change tone" submenu. */
export const TONE_VARIANTS: ToneVariant[] = Object.keys(TONE_LABELS) as ToneVariant[];

/** Translate variants for the "Translate" submenu. */
export const TRANSLATE_VARIANTS: TranslateVariant[] = Object.keys(
  TRANSLATE_LABELS,
) as TranslateVariant[];

export const TONE_LABEL = TONE_LABELS;
export const TRANSLATE_LABEL = TRANSLATE_LABELS;
