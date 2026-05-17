"use client";

import { type Editor, EditorContent, useEditor, useEditorState } from "@tiptap/react";
import Image from "@tiptap/extension-image";
import Link from "@tiptap/extension-link";
import StarterKit from "@tiptap/starter-kit";
import TaskList from "@tiptap/extension-task-list";
import TaskItem from "@tiptap/extension-task-item";
import Placeholder from "@tiptap/extension-placeholder";
import { Markdown } from "@tiptap/markdown";
import Typography from "@tiptap/extension-typography";
import {
  forwardRef,
  useCallback,
  useEffect,
  useImperativeHandle,
  useMemo,
  useRef,
  useState,
} from "react";
import { toast } from "sonner";
import {
  Bold,
  Code2,
  Heading1,
  Heading2,
  Heading3,
  ImageIcon,
  Italic,
  List,
  ListOrdered,
  ListTodo,
  MessageSquare,
  Minus,
  Quote,
  Sparkles,
  type LucideIcon,
} from "lucide-react";

import { cn } from "@/lib/utils";
import { normalizePastedEditorText } from "@/lib/utils/editor-paste";
import { Button } from "@/components/ui/button";
import { ALFRED_AI_STREAM_META } from "@/components/editor/editor-transaction-meta";
import { InlineAIPrompt, type AIPromptMode } from "@/components/editor/inline-ai-prompt";
import {
  AiStreamingController,
  type StreamingState,
} from "@/components/editor/ai-streaming-controller";
import { slashAICommands } from "@/lib/notes-ai/commands";
import { WikiLink, extractWikiLinkCardIds } from "@/components/editor/extensions/wiki-link";
import {
  WikiLinkAutocomplete,
  type WikiLinkAutocompleteItem,
  type WikiLinkSelection,
} from "@/components/editor/wiki-link-autocomplete";
import { BlockId } from "@/components/editor/extensions/block-id";
import { createZettelCard } from "@/lib/api/zettels";

function readEditorMarkdown(editor: Editor): string {
  const maybeGetMarkdown = (editor as unknown as { getMarkdown?: () => string }).getMarkdown;
  if (typeof maybeGetMarkdown === "function") {
    return maybeGetMarkdown.call(editor) ?? "";
  }

  const storage = editor.storage as unknown as { markdown?: { getMarkdown?: () => string } };
  return storage.markdown?.getMarkdown?.() ?? "";
}

export type MarkdownNotesEditorHandle = {
  appendMarkdown: (markdown: string) => void;
  flushPendingChanges: () => EditorDraft | null;
  getMarkdown: () => string;
  setMarkdown: (markdown: string) => void;
  getTiptapJson: () => Record<string, unknown> | null;
};

export type EditorDraft = {
  markdown: string;
  tiptapJson: Record<string, unknown> | null;
};

export type MarkdownNotesEditorProps = {
  markdown: string;
  tiptapJson?: Record<string, unknown> | null;
  documentTitle?: string;
  documentId?: string | null;
  onMarkdownChange?: (markdown: string) => void;
  onDraftChange?: (draft: EditorDraft) => void;
  onKeyboardCommand?: (command: "save") => void | Promise<void>;
  uploadImage?: (file: File) => Promise<string>;
  readOnly?: boolean;
  placeholder?: string;
  className?: string;
  autoFocus?: boolean;
  draftFlushDelayMs?: number;
  /** Card ID for AI suggestion context (first linked card). */
  contextCardId?: number;
  /** Called when wiki-links change so the parent can sync to backend. */
  onWikiLinksChange?: (cardIds: number[]) => void;
  /** Called when a wiki-link is clicked. */
  onWikiLinkClick?: (cardId: string) => void;
};

type SlashCommand = {
  title: string;
  description: string;
  keywords: string[];
  group: "Text" | "Lists" | "Media" | "AI";
  icon: LucideIcon;
  run: (editor: Editor) => void;
};

const EMPTY_PARAGRAPH_AI_DOUBLE_SPACE_MS = 400;
const DEFAULT_DRAFT_FLUSH_DELAY_MS = 320;
const FLOATING_VIEWPORT_PADDING = 12;

function asEditorJson(value: unknown): Record<string, unknown> | null {
  if (!value || typeof value !== "object") return null;
  return value as Record<string, unknown>;
}

function jsonSignature(value: Record<string, unknown> | null): string {
  if (!value) return "null";
  try {
    return JSON.stringify(value);
  } catch {
    return "";
  }
}

function setEditorContent(editor: Editor, draft: EditorDraft): void {
  if (draft.tiptapJson) {
    editor.commands.setContent(draft.tiptapJson);
    return;
  }
  editor.commands.setContent(draft.markdown, { contentType: "markdown" });
}

function constrainFloatingPosition(
  position: { top: number; left: number },
  size: { width: number; height: number },
): { top: number; left: number } {
  if (typeof window === "undefined") return position;
  return {
    top: Math.max(
      FLOATING_VIEWPORT_PADDING,
      Math.min(position.top, window.innerHeight - size.height - FLOATING_VIEWPORT_PADDING),
    ),
    left: Math.max(
      FLOATING_VIEWPORT_PADDING,
      Math.min(position.left, window.innerWidth - size.width - FLOATING_VIEWPORT_PADDING),
    ),
  };
}

function constrainCenteredLeft(left: number, width: number): number {
  if (typeof window === "undefined") return left;
  const halfWidth = width / 2;
  return Math.max(
    FLOATING_VIEWPORT_PADDING + halfWidth,
    Math.min(left, window.innerWidth - FLOATING_VIEWPORT_PADDING - halfWidth),
  );
}

async function fileToDataUrl(file: File): Promise<string> {
  const dataUrl = await new Promise<string>((resolve, reject) => {
    const reader = new FileReader();
    reader.onerror = () => reject(new Error("Failed to read image file."));
    reader.onload = () => resolve(String(reader.result ?? ""));
    reader.readAsDataURL(file);
  });

  if (!dataUrl) {
    throw new Error("Failed to read image file.");
  }
  return dataUrl;
}

function imageFilesFromDataTransfer(dataTransfer: DataTransfer | null | undefined): File[] {
  if (!dataTransfer) return [];

  const byNameAndSize = new Map<string, File>();
  for (const file of Array.from(dataTransfer.files ?? [])) {
    if (file.type.startsWith("image/")) {
      byNameAndSize.set(`${file.name}:${file.size}:${file.type}`, file);
    }
  }

  for (const item of Array.from(dataTransfer.items ?? [])) {
    if (item.kind !== "file" || !item.type.startsWith("image/")) continue;
    const file = item.getAsFile();
    if (file) {
      byNameAndSize.set(`${file.name}:${file.size}:${file.type}`, file);
    }
  }

  return Array.from(byNameAndSize.values());
}

export const MarkdownNotesEditor = forwardRef<MarkdownNotesEditorHandle, MarkdownNotesEditorProps>(
  function MarkdownNotesEditorImpl(
    {
      markdown,
      tiptapJson,
      documentTitle,
      documentId,
      onMarkdownChange,
      onDraftChange,
      onKeyboardCommand,
      uploadImage,
      readOnly,
      placeholder,
      className,
      autoFocus = true,
      draftFlushDelayMs = DEFAULT_DRAFT_FLUSH_DELAY_MS,
      contextCardId,
      onWikiLinksChange,
      onWikiLinkClick,
    },
    ref,
  ) {
    const [isFocused, setIsFocused] = useState(false);

    // Inline AI state
    const [aiPromptOpen, setAiPromptOpen] = useState(false);
    const [aiPromptMode, setAiPromptMode] = useState<AIPromptMode>("generate");
    const [aiPromptPosition, setAiPromptPosition] = useState<{ top: number; left: number }>({
      top: 0,
      left: 0,
    });
    const [aiTargetText, setAiTargetText] = useState("");
    const [aiTargetRange, setAiTargetRange] = useState<{ from: number; to: number } | null>(null);
    const [streamingState, setStreamingState] = useState<StreamingState>({ status: "idle" });
    const [streamInsertAt, setStreamInsertAt] = useState(0);
    const [streamOriginalRange, setStreamOriginalRange] = useState<{
      from: number;
      to: number;
      text: string;
    } | null>(null);

    // Wiki-link autocomplete state
    const [wikiQuery, setWikiQuery] = useState<string | null>(null);
    const [wikiPosition, setWikiPosition] = useState<{ top: number; left: number } | null>(null);
    const [wikiActiveIndex, setWikiActiveIndex] = useState(0);
    const [wikiTriggerPos, setWikiTriggerPos] = useState<number | null>(null);
    const wikiQueryRef = useRef<string | null>(null);
    const wikiActiveIndexRef = useRef(0);

    const [menuPosition, setMenuPosition] = useState<{ top: number; left: number } | null>(null);
    const [slashMenuPosition, setSlashMenuPosition] = useState<{
      top: number;
      left: number;
    } | null>(null);
    const [slashQuery, setSlashQuery] = useState<string | null>(null);
    const [slashActiveIndex, setSlashActiveIndex] = useState(0);

    const isFirstRender = useRef(true);

    const uploadImageRef = useRef(uploadImage);
    const onKeyboardCommandRef = useRef(onKeyboardCommand);
    const onMarkdownChangeRef = useRef(onMarkdownChange);
    const onDraftChangeRef = useRef(onDraftChange);
    const onWikiLinksChangeRef = useRef(onWikiLinksChange);
    const slashQueryRef = useRef<string | null>(null);
    const slashCommandsRef = useRef<SlashCommand[]>([]);
    const slashActiveIndexRef = useRef(0);
    const emptyParagraphSpaceAtRef = useRef<number | null>(null);
    const draftFlushTimerRef = useRef<number | null>(null);
    const lastNotifiedMarkdownRef = useRef(markdown);
    const lastNotifiedJsonSignatureRef = useRef(jsonSignature(tiptapJson ?? null));
    const activeDocumentIdRef = useRef(documentId ?? null);
    const streamingStatusRef = useRef<StreamingState["status"]>("idle");
    const wikiSelectableItemsRef = useRef<WikiLinkSelection[]>([]);
    const wikiCreateTitleRef = useRef<string | null>(null);
    const lastNotifiedWikiLinksRef = useRef("");

    const extensions = useMemo(
      () => [
        WikiLink.configure({
          onClickLink: (cardId: string) => {
            onWikiLinkClick?.(cardId);
          },
        }),
        StarterKit.configure({
          heading: {
            levels: [1, 2, 3],
          },
        }),
        BlockId.configure({
          types: [
            "paragraph",
            "heading",
            "blockquote",
            "codeBlock",
            "horizontalRule",
            "bulletList",
            "orderedList",
            "listItem",
            "taskList",
            "taskItem",
            "image",
          ],
          disabled: Boolean(readOnly),
        }),
        Link.configure({
          openOnClick: false,
          autolink: true,
          linkOnPaste: true,
        }),
        Image.configure({
          inline: false,
          allowBase64: true,
        }),
        TaskList.configure({
          HTMLAttributes: { class: "task-list" },
        }),
        TaskItem.configure({
          nested: true,
          HTMLAttributes: { class: "task-item" },
        }),
        Markdown,
        Typography,
        Placeholder.configure({
          placeholder: ({ node, editor: ed }) => {
            // First paragraph when editor is empty
            if (ed.isEmpty && node.type.name === "paragraph") {
              return placeholder ?? "Start writing...";
            }
            // Any other empty paragraph — keep hint minimal like Notion
            if (node.type.name === "paragraph" && node.textContent === "") {
              return "Type / for commands";
            }
            return "";
          },
          emptyEditorClass: "is-editor-empty",
        }),
      ],
      [placeholder, onWikiLinkClick, readOnly],
    );

    const updateMenuPosition = useCallback((editor: Editor) => {
      if (editor.state.selection.empty) {
        setMenuPosition(null);
        return;
      }

      const { from, to } = editor.state.selection;
      const start = editor.view.coordsAtPos(from);
      const end = editor.view.coordsAtPos(to);

      setMenuPosition({
        top: Math.max(FLOATING_VIEWPORT_PADDING, start.top - 48),
        left: constrainCenteredLeft((start.left + end.left) / 2, 220),
      });
    }, []);

    const openAI = useCallback((ed: Editor, modeOverride?: AIPromptMode) => {
      const { from, to } = ed.state.selection;
      const hasSelection = !ed.state.selection.empty;
      const { $from } = ed.state.selection;
      const paragraphText = $from.parent.textContent;

      let mode: AIPromptMode;
      let targetText: string;
      let targetRange: { from: number; to: number } | null;

      if (modeOverride) {
        mode = modeOverride;
      } else if (hasSelection) {
        mode = "transform";
      } else if (!paragraphText.trim()) {
        mode = "generate";
      } else {
        mode = "edit";
      }

      if (mode === "transform") {
        targetText = ed.state.doc.textBetween(from, to, " ");
        targetRange = { from, to };
      } else if (mode === "edit") {
        targetText = paragraphText;
        targetRange = { from: $from.start(), to: $from.end() };
      } else {
        targetText = "";
        targetRange = null;
      }

      const coords = ed.view.coordsAtPos(from);
      setAiPromptMode(mode);
      setAiTargetText(targetText);
      setAiTargetRange(targetRange);
      setAiPromptPosition(
        constrainFloatingPosition(
          { top: coords.bottom + 8, left: coords.left },
          { width: 420, height: 260 },
        ),
      );
      setAiPromptOpen(true);
    }, []);

    /**
     * Run an AI streaming request directly with a known instruction, without
     * showing the prompt. Used by `/ai-*` slash commands (Improve writing,
     * Continue writing, Brainstorm, etc.) where the instruction is fully
     * determined by the slash entry itself.
     *
     * Mirrors openAI's mode resolution: with-selection → transform context,
     * empty paragraph → generate (no original range), otherwise → edit on
     * the current paragraph.
     */
    const runAIInstruction = useCallback(
      (ed: Editor, instruction: string) => {
        const { from, to } = ed.state.selection;
        const hasSelection = !ed.state.selection.empty;
        const { $from } = ed.state.selection;
        const paragraphText = $from.parent.textContent;

        let targetText = "";
        let targetRange: { from: number; to: number } | null = null;

        if (hasSelection) {
          targetText = ed.state.doc.textBetween(from, to, " ");
          targetRange = { from, to };
        } else if (paragraphText.trim()) {
          targetText = paragraphText;
          targetRange = { from: $from.start(), to: $from.end() };
        }

        ed.commands.blur();
        const insertPos = targetRange ? targetRange.to : ed.state.selection.from;
        setStreamInsertAt(insertPos);
        setStreamOriginalRange(
          targetRange && targetText
            ? { from: targetRange.from, to: targetRange.to, text: targetText }
            : null,
        );
        setStreamingState({ status: "streaming", instruction });
      },
      [],
    );

    const aiSlashEntries = useMemo<SlashCommand[]>(
      () => {
        // The "Ask AI" entry opens the inline prompt with no preset
        // instruction so the user can free-form. Listed first so users
        // typing "/ai" land on it before any of the named commands.
        const askAI: SlashCommand = {
          title: "Ask AI",
          description: "Open the AI prompt to write or edit",
          keywords: ["ai", "ask", "prompt", "polymath"],
          group: "AI",
          icon: Sparkles,
          run: (ed) => {
            openAI(ed);
          },
        };

        // Each registry entry becomes a `/ai-<alias>` slash command. Panel
        // commands (Ask Polymath, Research) are skipped — they belong in
        // the inline flyout where they can route to the side panel without
        // confusing the slash → inline-stream flow.
        const named: SlashCommand[] = slashAICommands()
          .filter((cmd) => !cmd.panel)
          .map((cmd) => {
            const alias = cmd.slashAlias!;
            return {
              title: cmd.label,
              description: cmd.description ?? "",
              keywords: ["ai", alias, ...cmd.label.toLowerCase().split(/\s+/)],
              group: "AI",
              icon: cmd.icon,
              run: (ed) => runAIInstruction(ed, cmd.promptTemplate),
            };
          });

        return [askAI, ...named];
      },
      [openAI, runAIInstruction],
    );

    const slashCommands = useMemo<SlashCommand[]>(
      () => [
        {
          title: "Heading 1",
          description: "Large section heading",
          keywords: ["h1", "heading", "title"],
          group: "Text",
          icon: Heading1,
          run: (editor) => editor.chain().focus().toggleHeading({ level: 1 }).run(),
        },
        {
          title: "Heading 2",
          description: "Medium section heading",
          keywords: ["h2", "heading", "subtitle"],
          group: "Text",
          icon: Heading2,
          run: (editor) => editor.chain().focus().toggleHeading({ level: 2 }).run(),
        },
        {
          title: "Heading 3",
          description: "Small section heading",
          keywords: ["h3", "heading"],
          group: "Text",
          icon: Heading3,
          run: (editor) => editor.chain().focus().toggleHeading({ level: 3 }).run(),
        },
        {
          title: "Bulleted list",
          description: "Unordered list of items",
          keywords: ["bullet", "list", "ul"],
          group: "Lists",
          icon: List,
          run: (editor) => editor.chain().focus().toggleBulletList().run(),
        },
        {
          title: "Numbered list",
          description: "Ordered list of items",
          keywords: ["number", "list", "ol"],
          group: "Lists",
          icon: ListOrdered,
          run: (editor) => editor.chain().focus().toggleOrderedList().run(),
        },
        {
          title: "Todo list",
          description: "Task list with checkboxes",
          keywords: ["todo", "task", "checkbox", "check"],
          group: "Lists",
          icon: ListTodo,
          run: (editor) => editor.chain().focus().toggleTaskList().run(),
        },
        {
          title: "Quote",
          description: "Blockquote for emphasis",
          keywords: ["quote", "blockquote"],
          group: "Text",
          icon: Quote,
          run: (editor) => editor.chain().focus().toggleBlockquote().run(),
        },
        {
          title: "Code block",
          description: "Code with syntax highlighting",
          keywords: ["code", "block", "snippet"],
          group: "Text",
          icon: Code2,
          run: (editor) => editor.chain().focus().toggleCodeBlock().run(),
        },
        {
          title: "Divider",
          description: "Horizontal ruled line",
          keywords: ["divider", "hr", "separator"],
          group: "Media",
          icon: Minus,
          run: (editor) => editor.chain().focus().setHorizontalRule().run(),
        },
        {
          title: "Image",
          description: "Upload or paste an image",
          keywords: ["image", "photo", "picture", "img"],
          group: "Media",
          icon: ImageIcon,
          run: (editor) => {
            const input = document.createElement("input");
            input.type = "file";
            input.accept = "image/*";
            input.onchange = async () => {
              const file = input.files?.[0];
              if (!file) return;
              const uploader = uploadImageRef.current;
              try {
                const src = uploader ? await uploader(file) : await fileToDataUrl(file);
                if (!editor.isDestroyed) {
                  editor.chain().focus().setImage({ src, alt: file.name }).run();
                }
              } catch {
                toast.error("Failed to upload image");
              }
            };
            input.click();
          },
        },
        {
          title: "Callout",
          description: "Highlighted blockquote for emphasis",
          keywords: ["callout", "note", "info", "warning", "tip"],
          group: "Text",
          icon: MessageSquare,
          run: (editor) => editor.chain().focus().toggleBlockquote().run(),
        },
        // --- AI Slash Commands ---
        ...aiSlashEntries,
      ],
      [openAI, aiSlashEntries],
    );

    const filteredSlashCommands = useMemo(() => {
      if (slashQuery === null) return [];
      const query = slashQuery.trim().toLowerCase();
      if (!query) return slashCommands;
      return slashCommands.filter((cmd) => {
        if (cmd.title.toLowerCase().includes(query)) return true;
        return cmd.keywords.some((k) => k.toLowerCase().includes(query));
      });
    }, [slashCommands, slashQuery]);

    const updateSlashState = useCallback((editor: Editor) => {
      const { state } = editor;
      if (!editor.isEditable || !editor.isFocused) {
        setSlashQuery(null);
        setSlashMenuPosition(null);
        return;
      }
      if (!state.selection.empty) {
        setSlashQuery(null);
        setSlashMenuPosition(null);
        return;
      }

      const { $from } = state.selection;
      const parent = $from.parent;
      if (parent.type.name !== "paragraph") {
        setSlashQuery(null);
        setSlashMenuPosition(null);
        return;
      }

      const text = parent.textContent;
      if (!text.startsWith("/")) {
        setSlashQuery(null);
        setSlashMenuPosition(null);
        return;
      }
      if (text.includes(" ")) {
        setSlashQuery(null);
        setSlashMenuPosition(null);
        return;
      }
      if (state.selection.from !== $from.end()) {
        setSlashQuery(null);
        setSlashMenuPosition(null);
        return;
      }

      setSlashQuery(text.slice(1));
      const coords = editor.view.coordsAtPos(state.selection.from);
      setSlashMenuPosition(
        constrainFloatingPosition(
          { top: coords.bottom + 10, left: coords.left },
          { width: 320, height: 360 },
        ),
      );
    }, []);

    const updateWikiLinkState = useCallback((ed: Editor) => {
      if (!ed.isEditable || !ed.isFocused || !ed.state.selection.empty) {
        setWikiQuery(null);
        setWikiPosition(null);
        setWikiTriggerPos(null);
        return;
      }

      const { $from } = ed.state.selection;
      const textBefore = ed.state.doc.textBetween(Math.max(0, $from.pos - 100), $from.pos, "");

      // Find the last unclosed [[ (no ]] after it)
      const lastOpen = textBefore.lastIndexOf("[[");
      if (lastOpen === -1) {
        setWikiQuery(null);
        setWikiPosition(null);
        setWikiTriggerPos(null);
        return;
      }

      const afterOpen = textBefore.slice(lastOpen + 2);
      // If there's a ]] after [[, the link is closed
      if (afterOpen.includes("]]")) {
        setWikiQuery(null);
        setWikiPosition(null);
        setWikiTriggerPos(null);
        return;
      }

      // If there's a newline, don't span across paragraphs
      if (afterOpen.includes("\n")) {
        setWikiQuery(null);
        setWikiPosition(null);
        setWikiTriggerPos(null);
        return;
      }

      const query = afterOpen;
      const triggerAbsPos = $from.pos - afterOpen.length - 2;
      const coords = ed.view.coordsAtPos(triggerAbsPos);

      wikiQueryRef.current = query;
      setWikiQuery(query);
      setWikiPosition(
        constrainFloatingPosition(
          { top: coords.bottom + 8, left: coords.left },
          { width: 320, height: 360 },
        ),
      );
      setWikiTriggerPos(triggerAbsPos);
      wikiActiveIndexRef.current = 0;
      setWikiActiveIndex(0);
    }, []);

    const editorRef = useRef<Editor | null>(null);

    const handleWikiLinkSelect = useCallback(
      (selection: WikiLinkSelection) => {
        const ed = editorRef.current;
        if (!ed || ed.isDestroyed || wikiTriggerPos === null) return;
        const { from } = ed.state.selection;
        ed.chain()
          .focus()
          .deleteRange({ from: wikiTriggerPos, to: from })
          .insertWikiLink({ cardId: String(selection.cardId), title: selection.title })
          .run();
        setWikiQuery(null);
        setWikiPosition(null);
        setWikiTriggerPos(null);
        setWikiActiveIndex(0);

        setTimeout(() => {
          if (!ed.isDestroyed) {
            const json = ed.getJSON() as Record<string, unknown>;
            const cardIds = extractWikiLinkCardIds(json);
            lastNotifiedWikiLinksRef.current = cardIds.join(",");
            onWikiLinksChangeRef.current?.(cardIds);
          }
        }, 0);
      },
      [wikiTriggerPos],
    );

    const handleWikiLinkCreateStub = useCallback(
      async (title: string) => {
        const ed = editorRef.current;
        if (!ed || ed.isDestroyed || wikiTriggerPos === null) return;
        try {
          const card = await createZettelCard({ title, content: "" });
          handleWikiLinkSelect({ cardId: card.id, title: card.title });
        } catch {
          toast.error("Failed to create card");
        }
      },
      [wikiTriggerPos, handleWikiLinkSelect],
    );

    const handleWikiItemsChange = useCallback(
      (items: WikiLinkAutocompleteItem[], createTitle: string | null) => {
        wikiSelectableItemsRef.current = items.map((item) => ({
          cardId: item.cardId,
          title: item.title,
        }));
        wikiCreateTitleRef.current = createTitle;
        const selectableCount = items.length || (createTitle ? 1 : 0);
        if (selectableCount > 0 && wikiActiveIndexRef.current >= selectableCount) {
          wikiActiveIndexRef.current = selectableCount - 1;
          setWikiActiveIndex(selectableCount - 1);
        }
      },
      [],
    );

    const flushEditorDraft = useCallback(
      (ed: Editor, options: { force?: boolean } = {}): EditorDraft | null => {
        if (ed.isDestroyed) return null;

        const nextMarkdown = readEditorMarkdown(ed);
        const tiptapJson = asEditorJson(ed.getJSON());
        const nextJsonSignature = jsonSignature(tiptapJson);
        const markdownChanged = nextMarkdown !== lastNotifiedMarkdownRef.current;
        const jsonChanged = nextJsonSignature !== lastNotifiedJsonSignatureRef.current;

        if (options.force || markdownChanged) {
          lastNotifiedMarkdownRef.current = nextMarkdown;
          onMarkdownChangeRef.current?.(nextMarkdown);
        }

        if (options.force || markdownChanged || jsonChanged) {
          lastNotifiedJsonSignatureRef.current = nextJsonSignature;
          onDraftChangeRef.current?.({ markdown: nextMarkdown, tiptapJson });
        }

        if (tiptapJson && onWikiLinksChangeRef.current) {
          const wikiIds = extractWikiLinkCardIds(tiptapJson);
          const wikiKey = wikiIds.join(",");
          if (options.force || wikiKey !== lastNotifiedWikiLinksRef.current) {
            lastNotifiedWikiLinksRef.current = wikiKey;
            onWikiLinksChangeRef.current(wikiIds);
          }
        }

        return { markdown: nextMarkdown, tiptapJson };
      },
      [],
    );

    const clearDraftFlushTimer = useCallback(() => {
      if (draftFlushTimerRef.current === null) return;
      window.clearTimeout(draftFlushTimerRef.current);
      draftFlushTimerRef.current = null;
    }, []);

    const flushPendingEditorDraft = useCallback(
      (ed: Editor | null = editorRef.current, options: { force?: boolean } = {}) => {
        clearDraftFlushTimer();
        if (!ed || ed.isDestroyed) return null;
        return flushEditorDraft(ed, options);
      },
      [clearDraftFlushTimer, flushEditorDraft],
    );

    const scheduleDraftFlush = useCallback(
      (ed: Editor) => {
        clearDraftFlushTimer();
        draftFlushTimerRef.current = window.setTimeout(() => {
          draftFlushTimerRef.current = null;
          flushEditorDraft(ed);
        }, draftFlushDelayMs);
      },
      [clearDraftFlushTimer, draftFlushDelayMs, flushEditorDraft],
    );

    const editor = useEditor({
      extensions,
      content: tiptapJson ?? markdown,
      ...(tiptapJson ? {} : { contentType: "markdown" as const }),
      editable: !readOnly,
      immediatelyRender: false,
      shouldRerenderOnTransaction: false,
      editorProps: {
        attributes: {
          spellcheck: "false",
          class: cn(
            "alfred-note-prose prose dark:prose-invert max-w-none min-h-[220px] px-1 py-1 text-[16px] leading-[1.62] text-foreground focus:outline-none [text-wrap:pretty]",
            // Headings: editorial, not terminal-like.
            "prose-headings:mt-7 prose-headings:mb-2.5 prose-headings:font-sans prose-headings:font-medium prose-headings:tracking-[-0.015em]",
            "prose-h1:text-[1.85rem] prose-h2:text-[1.45rem] prose-h3:text-[1.15rem]",
            // Body: tighter scan rhythm for dense technical notes.
            "prose-p:my-3 prose-p:leading-[1.62] prose-p:text-left",
            // Code: subdued system voice.
            "prose-code:font-mono prose-code:text-[0.86em] prose-code:bg-secondary/80 prose-code:px-1.5 prose-code:py-0.5 prose-code:rounded-sm prose-code:before:content-none prose-code:after:content-none",
            "prose-pre:border prose-pre:border-[var(--alfred-ruled-line)] prose-pre:bg-card/70 prose-pre:text-foreground prose-pre:font-mono prose-pre:text-[13px] prose-pre:leading-relaxed prose-pre:rounded-md prose-pre:shadow-none",
            // Blockquote: semantic callout rather than markdown quote.
            "prose-blockquote:my-5 prose-blockquote:border-l-[3px] prose-blockquote:border-l-primary prose-blockquote:bg-[var(--alfred-accent-subtle)] prose-blockquote:px-4 prose-blockquote:py-3 prose-blockquote:not-italic prose-blockquote:rounded-r-md prose-blockquote:text-left",
            // Images
            "prose-img:rounded-lg prose-img:border prose-img:shadow-sm",
            // Links: accent color
            "prose-a:text-primary prose-a:no-underline hover:prose-a:underline",
            // HR: ruled line
            "prose-hr:my-7 prose-hr:border-[var(--alfred-ruled-line)]",
            // Lists
            "prose-ul:my-4 prose-ol:my-4 prose-li:my-1 prose-li:text-left prose-li:leading-[1.62]",
            // Task list: checkbox styling
            "[&_ul[data-type=taskList]]:list-none [&_ul[data-type=taskList]]:pl-2",
            "[&_li[data-type=taskItem]]:flex [&_li[data-type=taskItem]]:items-start [&_li[data-type=taskItem]]:gap-2 [&_li[data-type=taskItem]]:my-1.5",
            "[&_li[data-type=taskItem]>label]:flex [&_li[data-type=taskItem]>label]:items-center [&_li[data-type=taskItem]>label]:mt-0.5 [&_li[data-type=taskItem]>label]:shrink-0",
            "[&_li[data-type=taskItem]>label>input]:size-4 [&_li[data-type=taskItem]>label>input]:accent-[#E8590C] [&_li[data-type=taskItem]>label>input]:cursor-pointer",
            "[&_li[data-type=taskItem]>div]:flex-1 [&_li[data-type=taskItem]>div]:min-w-0",
            "[&_li[data-type=taskItem][data-checked=true]>div]:line-through [&_li[data-type=taskItem][data-checked=true]>div]:opacity-60",
            // Strong: slightly heavier
            "prose-strong:font-semibold",
          ),
        },
        transformPastedText: (text) => normalizePastedEditorText(text),
      },
      onUpdate: ({ editor, transaction }) => {
        if (!transaction.getMeta(ALFRED_AI_STREAM_META) && streamingStatusRef.current === "idle") {
          scheduleDraftFlush(editor);
        }
        updateMenuPosition(editor);
        updateSlashState(editor);
        updateWikiLinkState(editor);
      },
      onSelectionUpdate: ({ editor }) => {
        updateMenuPosition(editor);
        updateSlashState(editor);
        updateWikiLinkState(editor);
      },
      onFocus: () => setIsFocused(true),
      onBlur: ({ editor }) => {
        flushPendingEditorDraft(editor);
        setIsFocused(false);
        setSlashQuery(null);
        setSlashMenuPosition(null);
        setWikiQuery(null);
        setWikiPosition(null);
        setWikiTriggerPos(null);
        emptyParagraphSpaceAtRef.current = null;
      },
    });

    // Keep editorRef in sync for wiki-link callbacks
    useEffect(() => {
      editorRef.current = editor ?? null;
    }, [editor]);

    const formattingState = useEditorState({
      editor,
      selector: ({ editor: selectedEditor }) => ({
        isBold: selectedEditor?.isActive("bold") ?? false,
        isItalic: selectedEditor?.isActive("italic") ?? false,
      }),
    }) ?? { isBold: false, isItalic: false };

    useEffect(() => {
      streamingStatusRef.current = streamingState.status;
    }, [streamingState.status]);

    // Auto-focus: place cursor at end when editor mounts (Notion-like)
    useEffect(() => {
      if (!editor || readOnly || !autoFocus) return;
      // Small delay so the editor is fully mounted before focusing
      const timer = window.setTimeout(() => {
        if (editor.isDestroyed) return;
        editor.commands.focus("end");
      }, 50);
      return () => window.clearTimeout(timer);
      // Only run once when editor is first created
      // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [editor, autoFocus]);

    const runSlashCommand = useCallback(
      (command: SlashCommand) => {
        if (!editor || editor.isDestroyed) return;
        const { $from } = editor.state.selection;
        editor.chain().focus().deleteRange({ from: $from.start(), to: $from.end() }).run();
        command.run(editor);
        setSlashQuery(null);
        setSlashMenuPosition(null);
        setSlashActiveIndex(0);
      },
      [editor],
    );

    useEffect(() => {
      uploadImageRef.current = uploadImage;
    }, [uploadImage]);
    useEffect(() => {
      onKeyboardCommandRef.current = onKeyboardCommand;
    }, [onKeyboardCommand]);
    useEffect(() => {
      onMarkdownChangeRef.current = onMarkdownChange;
    }, [onMarkdownChange]);
    useEffect(() => {
      onDraftChangeRef.current = onDraftChange;
    }, [onDraftChange]);
    useEffect(() => {
      onWikiLinksChangeRef.current = onWikiLinksChange;
    }, [onWikiLinksChange]);
    useEffect(() => {
      slashQueryRef.current = slashQuery;
    }, [slashQuery]);
    useEffect(() => {
      slashCommandsRef.current = filteredSlashCommands;
    }, [filteredSlashCommands]);
    useEffect(() => {
      slashActiveIndexRef.current = slashActiveIndex;
    }, [slashActiveIndex]);

    useEffect(() => {
      if (slashQuery === null) {
        if (slashActiveIndexRef.current !== 0) slashActiveIndexRef.current = 0;
        if (slashActiveIndex !== 0) {
          const frame = window.requestAnimationFrame(() => setSlashActiveIndex(0));
          return () => window.cancelAnimationFrame(frame);
        }
        return;
      }
      slashActiveIndexRef.current = 0;
      if (slashActiveIndex !== 0) {
        const frame = window.requestAnimationFrame(() => setSlashActiveIndex(0));
        return () => window.cancelAnimationFrame(frame);
      }
    }, [slashActiveIndex, slashQuery]);

    useEffect(() => {
      if (!editor) return;
      if (slashActiveIndex >= filteredSlashCommands.length) {
        slashActiveIndexRef.current = 0;
        const frame = window.requestAnimationFrame(() => setSlashActiveIndex(0));
        return () => window.cancelAnimationFrame(frame);
      }
    }, [editor, filteredSlashCommands.length, slashActiveIndex]);

    const handleAISubmit = useCallback(
      (instruction: string) => {
        setAiPromptOpen(false);
        editor?.commands.blur();
        const insertPos = aiTargetRange ? aiTargetRange.to : (editor?.state.selection.from ?? 0);
        setStreamInsertAt(insertPos);
        setStreamOriginalRange(
          aiTargetRange && aiTargetText
            ? { from: aiTargetRange.from, to: aiTargetRange.to, text: aiTargetText }
            : null,
        );
        setStreamingState({ status: "streaming", instruction });
      },
      [editor, aiTargetRange, aiTargetText],
    );

    const handleStreamComplete = useCallback(() => {
      setStreamingState((prev) =>
        prev.status === "streaming" ? { status: "done", instruction: prev.instruction } : prev,
      );
    }, []);

    const handleStreamFinish = useCallback(
      (action: "accept" | "discard") => {
        if (action === "accept") {
          flushPendingEditorDraft(editor, { force: true });
          void Promise.resolve(onKeyboardCommandRef.current?.("save"));
        }
        setStreamingState({ status: "idle" });
        setStreamOriginalRange(null);
        editor?.commands.focus();
      },
      [editor, flushPendingEditorDraft],
    );

    const handleStreamFollowup = useCallback((instruction: string) => {
      // The streaming controller has already mutated the doc (or chosen not
      // to, for extend-mode follow-ups) — we just flip state back to
      // streaming with the new instruction. The controller's isFollowupRef
      // ensures it doesn't reset insertRangeRef on this re-entry.
      setStreamingState({ status: "streaming", instruction });
    }, []);

    const handleEditInstruction = useCallback(() => {
      // Discard current AI text, re-open prompt
      if (!editor) return;
      openAI(editor);
    }, [editor, openAI]);

    useEffect(() => {
      if (!editor) return;

      const dom = editor.view.dom;

      const onKeyDown = (event: KeyboardEvent) => {
        if (readOnly) return;

        const isMod = event.metaKey || event.ctrlKey;
        const key = event.key.toLowerCase();
        if (event.key !== " ") {
          emptyParagraphSpaceAtRef.current = null;
        }
        if (isMod && key === "s") {
          event.preventDefault();
          flushPendingEditorDraft(editor, { force: true });
          void Promise.resolve(onKeyboardCommandRef.current?.("save"));
          return;
        }

        if (isMod && key === "j") {
          event.preventDefault();
          event.stopPropagation();
          openAI(editor);
          return;
        }

        if (isMod && key === ";") {
          event.preventDefault();
          event.stopPropagation();
          openAI(editor);
          return;
        }

        // Double-space on an empty paragraph opens the AI prompt in generate mode.
        if (event.key === " " && !isMod && !event.shiftKey && !event.altKey) {
          const { $from } = editor.state.selection;
          const parent = $from.parent;
          if (
            parent.type.name === "paragraph" &&
            parent.textContent === "" &&
            editor.state.selection.empty
          ) {
            event.preventDefault();
            const now = Date.now();
            const lastSpaceAt = emptyParagraphSpaceAtRef.current;
            if (lastSpaceAt !== null && now - lastSpaceAt <= EMPTY_PARAGRAPH_AI_DOUBLE_SPACE_MS) {
              emptyParagraphSpaceAtRef.current = null;
              openAI(editor, "generate");
            } else {
              emptyParagraphSpaceAtRef.current = now;
            }
            return;
          }
          emptyParagraphSpaceAtRef.current = null;
        }

        // Wiki-link keyboard navigation
        if (wikiQueryRef.current !== null) {
          const wikiItems = wikiSelectableItemsRef.current;
          const createTitle = wikiCreateTitleRef.current;
          const wikiOptionCount = wikiItems.length || (createTitle ? 1 : 0);
          if (event.key === "Escape") {
            event.preventDefault();
            wikiQueryRef.current = null;
            setWikiQuery(null);
            setWikiPosition(null);
            setWikiTriggerPos(null);
            setWikiActiveIndex(0);
            return;
          }
          if (event.key === "ArrowDown") {
            event.preventDefault();
            const next =
              wikiOptionCount > 0
                ? (wikiActiveIndexRef.current + 1) % wikiOptionCount
                : wikiActiveIndexRef.current + 1;
            wikiActiveIndexRef.current = next;
            setWikiActiveIndex(next);
            return;
          }
          if (event.key === "ArrowUp") {
            event.preventDefault();
            const next =
              wikiOptionCount > 0
                ? (wikiActiveIndexRef.current - 1 + wikiOptionCount) % wikiOptionCount
                : Math.max(0, wikiActiveIndexRef.current - 1);
            wikiActiveIndexRef.current = next;
            setWikiActiveIndex(next);
            return;
          }
          if (event.key === "Enter" || event.key === "Tab") {
            event.preventDefault();
            const index = Math.max(
              0,
              Math.min(Math.max(wikiOptionCount - 1, 0), wikiActiveIndexRef.current),
            );
            const selected = wikiItems[index];
            if (selected) {
              handleWikiLinkSelect(selected);
              return;
            }
            if (createTitle) {
              void handleWikiLinkCreateStub(createTitle);
            }
            return;
          }
        }

        if (slashQueryRef.current === null) return;

        const commands = slashCommandsRef.current;
        if (event.key === "Escape") {
          event.preventDefault();
          slashQueryRef.current = null;
          slashActiveIndexRef.current = 0;
          setSlashQuery(null);
          setSlashMenuPosition(null);
          setSlashActiveIndex(0);
          return;
        }

        if (!commands.length) return;

        if (event.key === "ArrowDown") {
          event.preventDefault();
          const next = (slashActiveIndexRef.current + 1) % commands.length;
          slashActiveIndexRef.current = next;
          setSlashActiveIndex(next);
          return;
        }

        if (event.key === "ArrowUp") {
          event.preventDefault();
          const next = (slashActiveIndexRef.current - 1 + commands.length) % commands.length;
          slashActiveIndexRef.current = next;
          setSlashActiveIndex(next);
          return;
        }

        if (event.key === "Enter" || event.key === "Tab") {
          event.preventDefault();
          const idx = Math.max(0, Math.min(commands.length - 1, slashActiveIndexRef.current));
          const selected = commands[idx];

          const { $from } = editor.state.selection;
          editor.chain().focus().deleteRange({ from: $from.start(), to: $from.end() }).run();
          selected.run(editor);

          slashQueryRef.current = null;
          slashActiveIndexRef.current = 0;
          setSlashQuery(null);
          setSlashMenuPosition(null);
          setSlashActiveIndex(0);
        }
      };

      const onPaste = (event: ClipboardEvent) => {
        if (readOnly) return;
        const image = imageFilesFromDataTransfer(event.clipboardData)[0];
        if (!image) return;

        event.preventDefault();
        event.stopPropagation();
        void (async () => {
          const uploader = uploadImageRef.current;
          const src = uploader ? await uploader(image) : await fileToDataUrl(image);
          if (editor.isDestroyed) return;
          editor.chain().focus().setImage({ src, alt: image.name }).run();
        })().catch((err) => {
          toast.error(err instanceof Error ? err.message : "Failed to paste image.");
        });
      };

      const onDrop = (event: DragEvent) => {
        if (readOnly) return;
        const images = imageFilesFromDataTransfer(event.dataTransfer);
        if (!images.length) return;

        event.preventDefault();
        event.stopPropagation();
        void (async () => {
          const uploader = uploadImageRef.current;
          for (const image of images) {
            const src = uploader ? await uploader(image) : await fileToDataUrl(image);
            if (editor.isDestroyed) return;
            editor.chain().focus().setImage({ src, alt: image.name }).run();
          }
        })().catch((err) => {
          toast.error(err instanceof Error ? err.message : "Failed to drop image.");
        });
      };

      dom.addEventListener("keydown", onKeyDown, true);
      dom.addEventListener("paste", onPaste, true);
      dom.addEventListener("drop", onDrop, true);

      return () => {
        dom.removeEventListener("keydown", onKeyDown, true);
        dom.removeEventListener("paste", onPaste, true);
        dom.removeEventListener("drop", onDrop, true);
      };
    }, [
      editor,
      readOnly,
      openAI,
      flushPendingEditorDraft,
      handleWikiLinkCreateStub,
      handleWikiLinkSelect,
    ]);

    useEffect(() => {
      if (editor && editor.isEditable !== !readOnly) {
        editor.setEditable(!readOnly);
      }
    }, [editor, readOnly]);

    useEffect(() => {
      if (!editor) return;
      if (streamingState.status !== "idle") {
        isFirstRender.current = false;
        return;
      }
      const nextDraft = { markdown, tiptapJson: tiptapJson ?? null };
      const documentChanged = activeDocumentIdRef.current !== (documentId ?? null);
      const nextJsonSignature = jsonSignature(nextDraft.tiptapJson);
      const shouldReplaceContent =
        documentChanged ||
        isFirstRender.current ||
        (!isFocused &&
          (markdown !== lastNotifiedMarkdownRef.current ||
            nextJsonSignature !== lastNotifiedJsonSignatureRef.current));

      if (shouldReplaceContent) {
        clearDraftFlushTimer();
        setEditorContent(editor, nextDraft);
        activeDocumentIdRef.current = documentId ?? null;
        lastNotifiedMarkdownRef.current = markdown;
        lastNotifiedJsonSignatureRef.current = nextJsonSignature;
        if (nextDraft.tiptapJson) {
          lastNotifiedWikiLinksRef.current = extractWikiLinkCardIds(nextDraft.tiptapJson).join(",");
        } else {
          lastNotifiedWikiLinksRef.current = "";
        }
      }
      isFirstRender.current = false;
    }, [
      clearDraftFlushTimer,
      documentId,
      editor,
      isFocused,
      markdown,
      streamingState.status,
      tiptapJson,
    ]);

    useEffect(() => {
      return () => clearDraftFlushTimer();
    }, [clearDraftFlushTimer]);

    useImperativeHandle(
      ref,
      () => ({
        appendMarkdown: (nextMarkdown: string) => {
          if (!editor) return;
          const current = readEditorMarkdown(editor);
          const combined = current ? `${current}\n\n${nextMarkdown}` : nextMarkdown;
          editor.commands.setContent(combined, { contentType: "markdown" });
          editor.commands.scrollIntoView();
          flushPendingEditorDraft(editor, { force: true });
        },
        flushPendingChanges: () => flushPendingEditorDraft(editor, { force: true }),
        getMarkdown: () => (editor ? readEditorMarkdown(editor) : ""),
        setMarkdown: (nextMarkdown: string) => {
          editor?.commands.setContent(nextMarkdown, { contentType: "markdown" });
          if (editor) flushPendingEditorDraft(editor, { force: true });
        },
        getTiptapJson: () => (editor ? asEditorJson(editor.getJSON()) : null),
      }),
      [editor, flushPendingEditorDraft],
    );

    if (!editor) return null;

    return (
      <div
        className={cn(
          "relative flex h-full w-full flex-col overflow-visible bg-transparent transition-colors duration-200",
          isFocused && !readOnly && "",
          readOnly && "opacity-80",
          className,
        )}
      >
        {/* Wiki-link autocomplete */}
        {wikiPosition && wikiQuery !== null && !readOnly && (
          <WikiLinkAutocomplete
            query={wikiQuery}
            position={wikiPosition}
            contextCardId={contextCardId}
            activeIndex={wikiActiveIndex}
            onSelect={handleWikiLinkSelect}
            onCreateStub={handleWikiLinkCreateStub}
            onItemsChange={handleWikiItemsChange}
            onClose={() => {
              wikiQueryRef.current = null;
              setWikiQuery(null);
              setWikiPosition(null);
              setWikiTriggerPos(null);
              setWikiActiveIndex(0);
            }}
          />
        )}

        {/* Slash command menu */}
        {slashMenuPosition && slashQuery !== null && !readOnly ? (
          <div
            className="bg-card animate-in fade-in zoom-in-95 fixed z-50 w-80 overflow-hidden rounded-md border shadow-lg duration-100"
            style={{ top: `${slashMenuPosition.top}px`, left: `${slashMenuPosition.left}px` }}
          >
            {filteredSlashCommands.length ? (
              <div className="max-h-80 overflow-y-auto p-1.5">
                {filteredSlashCommands.map((cmd, idx) => {
                  const Icon = cmd.icon;
                  return (
                    <button
                      key={cmd.title}
                      type="button"
                      onMouseDown={(e) => {
                        e.preventDefault();
                        runSlashCommand(cmd);
                      }}
                      className={cn(
                        "grid w-full grid-cols-[28px_1fr_auto] items-center gap-2 rounded-md px-2.5 py-2 text-left transition-colors",
                        idx === slashActiveIndex
                          ? "text-foreground bg-[var(--alfred-accent-subtle)]"
                          : "text-muted-foreground hover:text-foreground hover:bg-[var(--alfred-accent-subtle)]",
                      )}
                    >
                      <span className="bg-secondary/70 flex size-7 items-center justify-center rounded-sm">
                        <Icon className="h-3.5 w-3.5" />
                      </span>
                      <span className="min-w-0">
                        <span className="block truncate text-sm font-medium">{cmd.title}</span>
                        <span className="block truncate text-[10px] text-[var(--alfred-text-tertiary)]">
                          {cmd.description}
                        </span>
                      </span>
                      <span className="font-mono text-[9px] text-[var(--alfred-text-tertiary)] uppercase">
                        {cmd.group}
                      </span>
                    </button>
                  );
                })}
              </div>
            ) : (
              <div className="px-3 py-2 text-[11px] text-[var(--alfred-text-tertiary)]">
                No commands found
              </div>
            )}
          </div>
        ) : null}

        {/* Slim bubble menu — B / I / AI */}
        {menuPosition && !editor.state.selection.empty && (
          <div
            className="bg-card animate-in fade-in zoom-in-95 fixed z-50 flex items-center gap-0.5 rounded-md border p-1 shadow-lg duration-100"
            style={{
              top: `${menuPosition.top}px`,
              left: `${menuPosition.left}px`,
              transform: "translateX(-50%)",
            }}
          >
            <Button
              variant="ghost"
              size="sm"
              onClick={() => editor.chain().focus().toggleBold().run()}
              aria-label="Bold"
              title="Bold"
              className={cn(
                "h-7 w-7 p-0",
                formattingState.isBold && "text-primary bg-[var(--alfred-accent-subtle)]",
              )}
            >
              <Bold className="h-3.5 w-3.5" />
            </Button>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => editor.chain().focus().toggleItalic().run()}
              aria-label="Italic"
              title="Italic"
              className={cn(
                "h-7 w-7 p-0",
                formattingState.isItalic && "text-primary bg-[var(--alfred-accent-subtle)]",
              )}
            >
              <Italic className="h-3.5 w-3.5" />
            </Button>

            <div className="bg-border mx-1 h-4 w-px" />

            <Button
              variant="ghost"
              size="sm"
              className="text-primary h-7 gap-1.5 px-2 text-[10px] font-medium uppercase hover:bg-[var(--alfred-accent-subtle)]"
              onClick={() => openAI(editor, "transform")}
            >
              <Sparkles className="h-3 w-3" />
              Ask AI
            </Button>
          </div>
        )}

        {/* Inline AI Prompt */}
        {aiPromptOpen && (
          <InlineAIPrompt
            editor={editor}
            mode={aiPromptMode}
            position={aiPromptPosition}
            targetText={aiTargetText}
            targetRange={aiTargetRange}
            onSubmit={handleAISubmit}
            onClose={() => {
              setAiPromptOpen(false);
              editor.commands.focus();
            }}
            isStreaming={streamingState.status === "streaming"}
          />
        )}

        {/* AI Streaming Controller */}
        {streamingState.status !== "idle" && (
          <AiStreamingController
            editor={editor}
            state={streamingState}
            insertAt={streamInsertAt}
            originalRange={streamOriginalRange}
            documentTitle={documentTitle}
            documentId={documentId}
            onStreamComplete={handleStreamComplete}
            onFinish={handleStreamFinish}
            onFollowup={handleStreamFollowup}
            onEditInstruction={handleEditInstruction}
          />
        )}

        <div
          className="flex-1 scroll-py-24 pb-24"
          onClick={() => editor.chain().focus().run()}
        >
          <EditorContent editor={editor} />
        </div>
      </div>
    );
  },
);

MarkdownNotesEditor.displayName = "MarkdownNotesEditor";
