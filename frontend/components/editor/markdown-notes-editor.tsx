"use client";

import { type Editor, EditorContent, useEditor } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
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
import { Separator } from "@/components/ui/separator";
import { completeText, rewriteText, summarizeText } from "@/lib/api/ai-assist";

type TiptapMarkdownStorage = {
  markdown?: {
    getMarkdown?: () => string;
  };
};

function readEditorMarkdown(editor: Editor): string {
  const storage = editor.storage as unknown as TiptapMarkdownStorage;
  return storage.markdown?.getMarkdown?.() ?? "";
}

export type MarkdownNotesEditorHandle = {
  appendMarkdown: (markdown: string) => void;
  getMarkdown: () => string;
  setMarkdown: (markdown: string) => void;
};

export type MarkdownNotesEditorProps = {
  markdown: string;
  onMarkdownChange?: (markdown: string) => void;
  readOnly?: boolean;
  placeholder?: string;
  className?: string;
};

export const MarkdownNotesEditor = forwardRef<MarkdownNotesEditorHandle, MarkdownNotesEditorProps>(
  function MarkdownNotesEditorImpl({ markdown, onMarkdownChange, readOnly, placeholder, className }, ref) {
    const [isFocused, setIsFocused] = useState(false);
    const [aiLoading, setAiLoading] = useState<"rewrite" | "complete" | "summarize" | null>(null);

    const [menuPosition, setMenuPosition] = useState<{ top: number; left: number } | null>(null);
    const isFirstRender = useRef(true);

    const extensions = useMemo(
      () => [
        StarterKit.configure({
          heading: {
            levels: [1, 2, 3],
          },
        }),
        Markdown,
        Typography,
        Placeholder.configure({
          placeholder: placeholder ?? "Write notes… (Select text for AI)",
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
        top: start.top - 40,
        left: (start.left + end.left) / 2,
      });
    }, []);

    const editor = useEditor({
      extensions,
      content: markdown,
      editable: !readOnly,
      immediatelyRender: false,
      editorProps: {
        attributes: {
          class: cn(
            "prose prose-sm dark:prose-invert max-w-none focus:outline-none min-h-[150px] px-4 py-3",
            "prose-headings:font-semibold prose-h1:text-2xl prose-h2:text-xl prose-h3:text-lg",
            "prose-pre:bg-muted prose-pre:text-foreground",
            "prose-blockquote:border-l-primary prose-blockquote:bg-muted/30 prose-blockquote:py-1 prose-blockquote:px-3 prose-blockquote:not-italic",
          ),
        },
      },
      onUpdate: ({ editor }) => {
        onMarkdownChange?.(readEditorMarkdown(editor));
        updateMenuPosition(editor);
      },
      onSelectionUpdate: ({ editor }) => updateMenuPosition(editor),
      onFocus: () => setIsFocused(true),
      onBlur: () => setIsFocused(false),
    });

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
          editor.commands.setContent(markdown);
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
          editor.commands.setContent(combined);
          editor.commands.scrollIntoView();
        },
        getMarkdown: () => (editor ? readEditorMarkdown(editor) : ""),
        setMarkdown: (nextMarkdown: string) => editor?.commands.setContent(nextMarkdown),
      }),
      [editor],
    );

    if (!editor) return null;

    return (
      <div
        className={cn(
          "bg-background ring-offset-background focus-within:ring-ring relative flex h-full w-full flex-col overflow-hidden rounded-xl border focus-within:ring-2 focus-within:ring-offset-2",
          readOnly && "opacity-80",
          className,
        )}
      >
        {menuPosition && !editor.state.selection.empty && (
          <div
            className="bg-popover animate-in fade-in zoom-in-95 fixed z-50 flex items-center gap-1 rounded-lg border p-1 shadow-lg duration-100"
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
                editor.isActive("bold") && "bg-accent text-accent-foreground",
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
                editor.isActive("italic") && "bg-accent text-accent-foreground",
              )}
            >
              <Italic className="h-3.5 w-3.5" />
            </Button>

            <Separator orientation="vertical" className="mx-1 h-4" />

            <Button
              variant="ghost"
              size="sm"
              className="h-7 gap-1.5 px-2 text-xs font-medium text-purple-600 hover:bg-purple-50 hover:text-purple-700 dark:text-purple-400 dark:hover:bg-purple-950/30"
              onClick={() => handleAiAction("rewrite")}
              disabled={!!aiLoading}
            >
              {aiLoading === "rewrite" ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
              ) : (
                <Wand2 className="h-3.5 w-3.5" />
              )}
              Rewrite
            </Button>
            <Button
              variant="ghost"
              size="sm"
              className="h-7 gap-1.5 px-2 text-xs font-medium text-orange-600 hover:bg-orange-50 hover:text-orange-700 dark:text-orange-400 dark:hover:bg-orange-950/30"
              onClick={() => handleAiAction("summarize")}
              disabled={!!aiLoading}
            >
              {aiLoading === "summarize" ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
              ) : (
                <FileText className="h-3.5 w-3.5" />
              )}
              Summarize
            </Button>
            <Button
              variant="ghost"
              size="sm"
              className="h-7 gap-1.5 px-2 text-xs font-medium text-blue-600 hover:bg-blue-50 hover:text-blue-700 dark:text-blue-400 dark:hover:bg-blue-950/30"
              onClick={() => handleAiAction("complete")}
              disabled={!!aiLoading}
            >
              {aiLoading === "complete" ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
              ) : (
                <PenLine className="h-3.5 w-3.5" />
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

