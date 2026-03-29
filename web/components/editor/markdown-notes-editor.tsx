"use client";

import { type Editor, EditorContent, useEditor } from "@tiptap/react";
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
import { Bold, FileText, Italic, Loader2, PenLine, Wand2 } from "lucide-react";

import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { completeText, rewriteText, summarizeText } from "@/lib/api/ai-assist";

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
  getMarkdown: () => string;
  setMarkdown: (markdown: string) => void;
  getTiptapJson: () => Record<string, unknown> | null;
};

export type MarkdownNotesEditorProps = {
  markdown: string;
  onMarkdownChange?: (markdown: string) => void;
  onDraftChange?: (draft: { markdown: string; tiptapJson: Record<string, unknown> }) => void;
  onKeyboardCommand?: (command: "save") => void | Promise<void>;
  uploadImage?: (file: File) => Promise<string>;
  readOnly?: boolean;
  placeholder?: string;
  className?: string;
};

type SlashCommand = {
  title: string;
  description: string;
  keywords: string[];
  run: (editor: Editor) => void;
};

function asEditorJson(value: unknown): Record<string, unknown> | null {
  if (!value || typeof value !== "object") return null;
  return value as Record<string, unknown>;
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

export const MarkdownNotesEditor = forwardRef<MarkdownNotesEditorHandle, MarkdownNotesEditorProps>(
  function MarkdownNotesEditorImpl(
    { markdown, onMarkdownChange, onDraftChange, onKeyboardCommand, uploadImage, readOnly, placeholder, className },
    ref,
  ) {
    const [isFocused, setIsFocused] = useState(false);
    const [aiLoading, setAiLoading] = useState<"rewrite" | "complete" | "summarize" | null>(null);

    const [menuPosition, setMenuPosition] = useState<{ top: number; left: number } | null>(null);
    const [slashMenuPosition, setSlashMenuPosition] = useState<{ top: number; left: number } | null>(null);
    const [slashQuery, setSlashQuery] = useState<string | null>(null);
    const [slashActiveIndex, setSlashActiveIndex] = useState(0);
    const isFirstRender = useRef(true);

    const uploadImageRef = useRef(uploadImage);
    const onKeyboardCommandRef = useRef(onKeyboardCommand);
    const slashQueryRef = useRef<string | null>(null);
    const slashCommandsRef = useRef<SlashCommand[]>([]);
    const slashActiveIndexRef = useRef(0);

    const extensions = useMemo(
      () => [
        StarterKit.configure({
          heading: {
            levels: [1, 2, 3],
          },
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
          placeholder: placeholder ?? "Start writing...",
          emptyEditorClass: "is-editor-empty",
        }),
      ],
      [placeholder],
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
        top: start.top - 48,
        left: (start.left + end.left) / 2,
      });
    }, []);

    const slashCommands = useMemo<SlashCommand[]>(
      () => [
        {
          title: "Heading 1",
          description: "Large section heading",
          keywords: ["h1", "heading", "title"],
          run: (editor) => editor.chain().focus().toggleHeading({ level: 1 }).run(),
        },
        {
          title: "Heading 2",
          description: "Medium section heading",
          keywords: ["h2", "heading", "subtitle"],
          run: (editor) => editor.chain().focus().toggleHeading({ level: 2 }).run(),
        },
        {
          title: "Heading 3",
          description: "Small section heading",
          keywords: ["h3", "heading"],
          run: (editor) => editor.chain().focus().toggleHeading({ level: 3 }).run(),
        },
        {
          title: "Bulleted list",
          description: "Unordered list of items",
          keywords: ["bullet", "list", "ul"],
          run: (editor) => editor.chain().focus().toggleBulletList().run(),
        },
        {
          title: "Numbered list",
          description: "Ordered list of items",
          keywords: ["number", "list", "ol"],
          run: (editor) => editor.chain().focus().toggleOrderedList().run(),
        },
        {
          title: "Todo list",
          description: "Task list with checkboxes",
          keywords: ["todo", "task", "checkbox", "check"],
          run: (editor) => editor.chain().focus().toggleTaskList().run(),
        },
        {
          title: "Quote",
          description: "Blockquote for emphasis",
          keywords: ["quote", "blockquote"],
          run: (editor) => editor.chain().focus().toggleBlockquote().run(),
        },
        {
          title: "Code block",
          description: "Code with syntax highlighting",
          keywords: ["code", "block", "snippet"],
          run: (editor) => editor.chain().focus().toggleCodeBlock().run(),
        },
        {
          title: "Divider",
          description: "Horizontal ruled line",
          keywords: ["divider", "hr", "separator"],
          run: (editor) => editor.chain().focus().setHorizontalRule().run(),
        },
      ],
      [],
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
      setSlashMenuPosition({ top: coords.bottom + 10, left: coords.left });
    }, []);

    const editor = useEditor({
      extensions,
      content: markdown,
      contentType: "markdown",
      editable: !readOnly,
      immediatelyRender: false,
      editorProps: {
        attributes: {
          class: cn(
            "prose prose-sm dark:prose-invert max-w-none focus:outline-none min-h-[150px] px-4 py-3",
            // Headings: Instrument Serif
            "prose-headings:font-serif prose-headings:tracking-tight prose-headings:font-normal",
            "prose-h1:text-3xl prose-h2:text-2xl prose-h3:text-xl",
            // Body: DM Sans (inherits from font-sans)
            "prose-p:leading-relaxed",
            // Code: JetBrains Mono
            "prose-code:font-mono prose-code:text-[13px] prose-code:bg-secondary prose-code:px-1.5 prose-code:py-0.5 prose-code:rounded-sm prose-code:before:content-none prose-code:after:content-none",
            "prose-pre:bg-secondary prose-pre:text-foreground prose-pre:font-mono prose-pre:text-[13px] prose-pre:rounded-md",
            // Blockquote: accent left border
            "prose-blockquote:border-l-primary prose-blockquote:bg-[var(--alfred-accent-subtle)] prose-blockquote:py-1 prose-blockquote:px-4 prose-blockquote:not-italic prose-blockquote:rounded-r-md",
            // Images
            "prose-img:rounded-lg prose-img:border prose-img:shadow-sm",
            // Links: accent color
            "prose-a:text-primary prose-a:no-underline hover:prose-a:underline",
            // HR: ruled line
            "prose-hr:border-[var(--alfred-ruled-line)]",
            // Strong: slightly heavier
            "prose-strong:font-semibold",
          ),
        },
      },
      onUpdate: ({ editor }) => {
        const nextMarkdown = readEditorMarkdown(editor);
        onMarkdownChange?.(nextMarkdown);
        const tiptapJson = asEditorJson(editor.getJSON());
        if (tiptapJson) {
          onDraftChange?.({ markdown: nextMarkdown, tiptapJson });
        }
        updateMenuPosition(editor);
        updateSlashState(editor);
      },
      onSelectionUpdate: ({ editor }) => {
        updateMenuPosition(editor);
        updateSlashState(editor);
      },
      onFocus: () => setIsFocused(true),
      onBlur: () => {
        setIsFocused(false);
        setSlashQuery(null);
        setSlashMenuPosition(null);
      },
    });

    const runSlashCommand = useCallback(
      (command: SlashCommand) => {
        if (!editor || editor.isDestroyed) return;
        const { $from } = editor.state.selection;
        editor
          .chain()
          .focus()
          .deleteRange({ from: $from.start(), to: $from.end() })
          .run();
        command.run(editor);
        setSlashQuery(null);
        setSlashMenuPosition(null);
        setSlashActiveIndex(0);
      },
      [editor],
    );

    useEffect(() => { uploadImageRef.current = uploadImage; }, [uploadImage]);
    useEffect(() => { onKeyboardCommandRef.current = onKeyboardCommand; }, [onKeyboardCommand]);
    useEffect(() => { slashQueryRef.current = slashQuery; }, [slashQuery]);
    useEffect(() => { slashCommandsRef.current = filteredSlashCommands; }, [filteredSlashCommands]);
    useEffect(() => { slashActiveIndexRef.current = slashActiveIndex; }, [slashActiveIndex]);

    useEffect(() => {
      if (slashQuery === null) {
        if (slashActiveIndexRef.current !== 0) slashActiveIndexRef.current = 0;
        if (slashActiveIndex !== 0) setSlashActiveIndex(0);
        return;
      }
      slashActiveIndexRef.current = 0;
      if (slashActiveIndex !== 0) setSlashActiveIndex(0);
    }, [slashActiveIndex, slashQuery]);

    useEffect(() => {
      if (!editor) return;
      if (slashActiveIndex >= filteredSlashCommands.length) {
        slashActiveIndexRef.current = 0;
        setSlashActiveIndex(0);
      }
    }, [editor, filteredSlashCommands.length, slashActiveIndex]);

    useEffect(() => {
      if (!editor) return;

      const dom = editor.view.dom;

      const onKeyDown = (event: KeyboardEvent) => {
        if (readOnly) return;

        const isMod = event.metaKey || event.ctrlKey;
        const key = event.key.toLowerCase();
        if (isMod && key === "s") {
          event.preventDefault();
          void Promise.resolve(onKeyboardCommandRef.current?.("save"));
          return;
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
          editor
            .chain()
            .focus()
            .deleteRange({ from: $from.start(), to: $from.end() })
            .run();
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
        const files = Array.from(event.clipboardData?.files ?? []);
        const image = files.find((file) => file.type.startsWith("image/"));
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
        const files = Array.from(event.dataTransfer?.files ?? []);
        const images = files.filter((file) => file.type.startsWith("image/"));
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
    }, [editor, readOnly]);

    const handleAiAction = async (action: "rewrite" | "complete" | "summarize") => {
      if (!editor) return;

      const { from, to } = editor.state.selection;
      const selectedText = editor.state.doc.textBetween(from, to, " ");
      if (!selectedText && (action === "rewrite" || action === "summarize")) return;

      setAiLoading(action);
      try {
        let result = "";
        if (action === "rewrite") {
          result = await rewriteText(selectedText);
        } else if (action === "summarize") {
          result = await summarizeText(selectedText);
        } else {
          const before = editor.state.doc.textBetween(Math.max(0, from - 500), from, " ");
          const after = editor.state.doc.textBetween(
            to,
            Math.min(editor.state.doc.content.size, to + 500),
            " ",
          );
          result = selectedText
            ? await completeText(selectedText, before, after)
            : await completeText(before, before, after);
        }

        if (editor.isDestroyed) return;

        if (action === "complete") {
          editor.view.dispatch(editor.state.tr.insertText(result, to));
          toast.success("Continued with AI");
        } else {
          editor.commands.insertContent(result);
          toast.success(action === "rewrite" ? "Rewritten with AI" : "Summarized with AI");
        }
      } catch (err) {
        toast.error(err instanceof Error ? err.message : "AI action failed");
      } finally {
        setAiLoading(null);
        setMenuPosition(null);
      }
    };

    useEffect(() => {
      if (editor && editor.isEditable !== !readOnly) {
        editor.setEditable(!readOnly);
      }
    }, [editor, readOnly]);

    useEffect(() => {
      if (!editor) return;
      const currentContent = readEditorMarkdown(editor);
      if (markdown !== currentContent) {
        if (!isFocused || isFirstRender.current) {
          editor.commands.setContent(markdown, { contentType: "markdown" });
        }
      }
      isFirstRender.current = false;
    }, [editor, markdown, isFocused]);

    useImperativeHandle(
      ref,
      () => ({
        appendMarkdown: (nextMarkdown: string) => {
          if (!editor) return;
          const current = readEditorMarkdown(editor);
          const combined = current ? `${current}\n\n${nextMarkdown}` : nextMarkdown;
          editor.commands.setContent(combined, { contentType: "markdown" });
          editor.commands.scrollIntoView();
        },
        getMarkdown: () => (editor ? readEditorMarkdown(editor) : ""),
        setMarkdown: (nextMarkdown: string) =>
          editor?.commands.setContent(nextMarkdown, { contentType: "markdown" }),
        getTiptapJson: () => (editor ? asEditorJson(editor.getJSON()) : null),
      }),
      [editor],
    );

    if (!editor) return null;

    return (
      <div
        className={cn(
          "relative flex h-full w-full flex-col overflow-hidden rounded-lg border bg-background",
          readOnly && "opacity-80",
          className,
        )}
      >
        {/* Slash command menu */}
        {slashMenuPosition && slashQuery !== null && !readOnly ? (
          <div
            className="fixed z-50 w-64 overflow-hidden rounded-md border bg-card shadow-lg animate-in fade-in zoom-in-95 duration-100"
            style={{ top: `${slashMenuPosition.top}px`, left: `${slashMenuPosition.left}px` }}
          >
            {filteredSlashCommands.length ? (
              <div className="max-h-64 overflow-y-auto p-1">
                {filteredSlashCommands.map((cmd, idx) => (
                  <button
                    key={cmd.title}
                    type="button"
                    onMouseDown={(e) => {
                      e.preventDefault();
                      runSlashCommand(cmd);
                    }}
                    className={cn(
                      "flex w-full flex-col gap-0.5 rounded-md px-3 py-2 text-left transition-colors",
                      idx === slashActiveIndex
                        ? "bg-[var(--alfred-accent-subtle)] text-foreground"
                        : "text-muted-foreground hover:bg-[var(--alfred-accent-subtle)] hover:text-foreground",
                    )}
                  >
                    <span className="text-sm font-medium">{cmd.title}</span>
                    <span className="font-mono text-[10px] text-[var(--alfred-text-tertiary)]">{cmd.description}</span>
                  </button>
                ))}
              </div>
            ) : (
              <div className="px-3 py-2 font-mono text-[11px] text-[var(--alfred-text-tertiary)]">No commands found</div>
            )}
          </div>
        ) : null}

        {/* AI bubble menu — appears on text selection */}
        {menuPosition && !editor.state.selection.empty && (
          <div
            className="fixed z-50 flex items-center gap-0.5 rounded-md border bg-card p-1 shadow-lg animate-in fade-in zoom-in-95 duration-100"
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
              className={cn(
                "h-7 w-7 p-0",
                editor.isActive("bold") && "bg-[var(--alfred-accent-subtle)] text-primary",
              )}
            >
              <Bold className="h-3.5 w-3.5" />
            </Button>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => editor.chain().focus().toggleItalic().run()}
              className={cn(
                "h-7 w-7 p-0",
                editor.isActive("italic") && "bg-[var(--alfred-accent-subtle)] text-primary",
              )}
            >
              <Italic className="h-3.5 w-3.5" />
            </Button>

            <div className="mx-1 h-4 w-px bg-border" />

            <Button
              variant="ghost"
              size="sm"
              className="h-7 gap-1.5 px-2 font-mono text-[10px] uppercase tracking-wider text-primary hover:bg-[var(--alfred-accent-subtle)]"
              onClick={() => handleAiAction("rewrite")}
              disabled={!!aiLoading}
            >
              {aiLoading === "rewrite" ? (
                <Loader2 className="h-3 w-3 animate-spin" />
              ) : (
                <Wand2 className="h-3 w-3" />
              )}
              Rewrite
            </Button>
            <Button
              variant="ghost"
              size="sm"
              className="h-7 gap-1.5 px-2 font-mono text-[10px] uppercase tracking-wider text-muted-foreground hover:bg-[var(--alfred-accent-subtle)] hover:text-foreground"
              onClick={() => handleAiAction("summarize")}
              disabled={!!aiLoading}
            >
              {aiLoading === "summarize" ? (
                <Loader2 className="h-3 w-3 animate-spin" />
              ) : (
                <FileText className="h-3 w-3" />
              )}
              Summarize
            </Button>
            <Button
              variant="ghost"
              size="sm"
              className="h-7 gap-1.5 px-2 font-mono text-[10px] uppercase tracking-wider text-muted-foreground hover:bg-[var(--alfred-accent-subtle)] hover:text-foreground"
              onClick={() => handleAiAction("complete")}
              disabled={!!aiLoading}
            >
              {aiLoading === "complete" ? (
                <Loader2 className="h-3 w-3 animate-spin" />
              ) : (
                <PenLine className="h-3 w-3" />
              )}
              Continue
            </Button>
          </div>
        )}

        <div className="flex-1 overflow-y-auto" onClick={() => editor.chain().focus().run()}>
          <EditorContent editor={editor} />
        </div>
      </div>
    );
  },
);

MarkdownNotesEditor.displayName = "MarkdownNotesEditor";
