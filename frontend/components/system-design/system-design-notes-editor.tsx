"use client";

import {
  EditorContent,
  useEditor,
} from "@tiptap/react";
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
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import {
  Bold,
  Italic,
  Strikethrough,
  Code,
  List,
  ListOrdered,
  Quote,
  Sparkles,
  Heading1,
  Heading2,
  CheckSquare,
  Wand2,
  PenLine,
  Loader2,
  FileText,
} from "lucide-react";
import { Separator } from "@/components/ui/separator";
import { completeText, rewriteText, summarizeText } from "@/lib/api/ai-assist";
import { toast } from "sonner";

export type SystemDesignNotesEditorHandle = {
  appendMarkdown: (markdown: string) => void;
  getMarkdown: () => string;
  setMarkdown: (markdown: string) => void;
};

export type SystemDesignNotesEditorProps = {
  markdown: string;
  onMarkdownChange?: (markdown: string) => void;
  readOnly?: boolean;
  placeholder?: string;
  className?: string; // Allow custom class names
};

export const SystemDesignNotesEditor = forwardRef<
  SystemDesignNotesEditorHandle,
  SystemDesignNotesEditorProps
>(function SystemDesignNotesEditorImpl(
  { markdown, onMarkdownChange, readOnly, placeholder, className },
  ref,
) {
  // We use validMarkdown to track the latest markdown value to prevent stale closures in onUpdate,
  // while also avoiding re-creating the editor on every markdown prop change.
  const [isFocused, setIsFocused] = useState(false);
  const [aiLoading, setAiLoading] = useState<string | null>(null);

  // Custom bubble menu state
  const [menuPosition, setMenuPosition] = useState<{ top: number; left: number } | null>(null);
  const menuRef = useRef<HTMLDivElement>(null);

  // To prevent loops where the editor updates -> triggers onMarkdownChange -> updates prop -> resets editor cursor
  // we only setContent if the content is significantly different or if it's the initial load.
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
        placeholder: placeholder ?? "Write notes… (Type '/' for commands)",
        emptyEditorClass: "is-editor-empty",
      }),
    ],
    [placeholder],
  );

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
      // @ts-ignore - tiptap-markdown storage typing issue
      onMarkdownChange?.(editor.storage.markdown?.getMarkdown?.() ?? "");
      updateMenuPosition(editor);
    },
    onSelectionUpdate: ({ editor }) => {
      updateMenuPosition(editor);
    },
    onFocus: () => setIsFocused(true),
    onBlur: () => {
      setIsFocused(false);
      // setMenuPosition(null); // Optional: hide on blur
    },
  });

  const updateMenuPosition = useCallback((editor: any) => {
    if (editor.state.selection.empty) {
      setMenuPosition(null);
      return;
    }

    const { from, to } = editor.state.selection;
    const start = editor.view.coordsAtPos(from);
    const end = editor.view.coordsAtPos(to);

    // Calculate center of selection
    const left = (start.left + end.left) / 2;
    const top = start.top - 40; // Position above

    // Relative to viewport is fine for fixed/absolute, but we need to account for container if we use absolute.
    // For simplicity, we'll use fixed positioning for the menu or ensure the container allows it.
    // We'll return client coordinates and use fixed positioning.

    setMenuPosition({ top, left });
  }, []);

  const handleAiAction = async (action: 'rewrite' | 'complete' | 'summarize') => {
    if (!editor) return;
    const { from, to, empty } = editor.state.selection;
    const text = editor.state.doc.textBetween(from, to, " ");

    if (!text && (action === 'rewrite' || action === 'summarize')) return;

    setAiLoading(action);
    try {
      let result = "";
      if (action === 'rewrite') {
        result = await rewriteText(text);
      } else if (action === 'summarize') {
        result = await summarizeText(text);
      } else if (action === 'complete') {
        // Get context
        const before = editor.state.doc.textBetween(Math.max(0, from - 500), from, " ");
        const after = editor.state.doc.textBetween(to, Math.min(editor.state.doc.content.size, to + 500), " ");
        result = await completeText(text || before, text ? "" : before, after);

        if (text) {
          result = await completeText(text, before, after);
        } else {
          result = await completeText(before, before, after);
        }
      }

      if (editor.isDestroyed) return;

      if (action === 'rewrite') {
        editor.commands.insertContent(result);
        toast.success("Rewritten with AI");
      } else if (action === 'summarize') {
        // Insert summary after selection or replace? Let's replace for now or append.
        // Usually summary replaces or is shown elsewhere. Let's replace for "Summarize this section" flow.
        editor.commands.insertContent(result);
        toast.success("Summarized with AI");
      } else {
        // Append completion
        const transaction = editor.state.tr.insertText(result, to);
        editor.view.dispatch(transaction);
        toast.success("Completed with AI");
      }
    } catch (err) {
      toast.error("AI action failed");
    } finally {
      setAiLoading(null);
      setMenuPosition(null); // Hide menu after action
    }
  };

  // Sync editability
  useEffect(() => {
    if (editor && editor.isEditable !== !readOnly) {
      editor.setEditable(!readOnly);
    }
  }, [editor, readOnly]);

  // Sync external content changes (carefully)
  useEffect(() => {
    if (!editor) return;

    // @ts-ignore - tiptap-markdown storage typing issue
    const currentContent = editor.storage.markdown?.getMarkdown?.() ?? "";
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
        // @ts-ignore - tiptap-markdown storage typing issue
        const current = editor.storage.markdown?.getMarkdown?.() ?? "";
        const combined = current ? `${current}\n\n${nextMarkdown}` : nextMarkdown;
        editor.commands.setContent(combined);
        // Scroll to bottom
        editor.commands.scrollIntoView();
      },
      // @ts-ignore - tiptap-markdown storage typing issue
      getMarkdown: () => editor?.storage.markdown?.getMarkdown?.() ?? "",
      setMarkdown: (nextMarkdown: string) => {
        editor?.commands.setContent(nextMarkdown);
      },
    }),
    [editor],
  );

  if (!editor) {
    return null;
  }

  return (
    <div
      className={cn(
        "relative flex h-full w-full flex-col overflow-hidden rounded-xl border bg-background ring-offset-background focus-within:ring-2 focus-within:ring-ring focus-within:ring-offset-2",
        readOnly && "opacity-80",
        className
      )}
    >
      {/* Custom Floating Menu */}
      {menuPosition && editor && !editor.state.selection.empty && (
        <div
          ref={menuRef}
          className="fixed z-50 flex items-center gap-1 rounded-lg border bg-popover p-1 shadow-lg animate-in fade-in zoom-in-95 duration-100"
          style={{
            top: `${menuPosition.top}px`,
            left: `${menuPosition.left}px`,
            transform: 'translateX(-50%)',
          }}
        >
          <Button
            variant="ghost"
            size="sm"
            onClick={() => editor.chain().focus().toggleBold().run()}
            className={cn("h-7 w-7 p-0", editor.isActive("bold") && "bg-accent text-accent-foreground")}
          >
            <Bold className="h-3.5 w-3.5" />
          </Button>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => editor.chain().focus().toggleItalic().run()}
            className={cn("h-7 w-7 p-0", editor.isActive("italic") && "bg-accent text-accent-foreground")}
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
            {aiLoading === 'rewrite' ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Wand2 className="h-3.5 w-3.5" />}
            Rewrite
          </Button>
          <Button
            variant="ghost"
            size="sm"
            className="h-7 gap-1.5 px-2 text-xs font-medium text-orange-600 hover:bg-orange-50 hover:text-orange-700 dark:text-orange-400 dark:hover:bg-orange-950/30"
            onClick={() => handleAiAction("summarize")}
            disabled={!!aiLoading}
          >
            {aiLoading === 'summarize' ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <FileText className="h-3.5 w-3.5" />}
            Summarize
          </Button>
          <Button
            variant="ghost"
            size="sm"
            className="h-7 gap-1.5 px-2 text-xs font-medium text-blue-600 hover:bg-blue-50 hover:text-blue-700 dark:text-blue-400 dark:hover:bg-blue-950/30"
            onClick={() => handleAiAction("complete")}
            disabled={!!aiLoading}
          >
            {aiLoading === 'complete' ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <PenLine className="h-3.5 w-3.5" />}
            Continue
          </Button>
        </div>
      )}

      {/* Editor Content */}
      <div className="flex-1 overflow-y-auto" onClick={() => editor.chain().focus().run()}>
        <EditorContent editor={editor} />
      </div>

      {/* Optional Footer / Status */}
      {!readOnly && (
        <div className="flex items-center justify-between border-t bg-muted/20 px-3 py-1.5 text-xs text-muted-foreground">
          <div className="flex items-center gap-2">
            <span>Markdown supported</span>
          </div>
          <div className="flex items-center gap-2">
            {editor.storage.characterCount?.characters()} chars
          </div>
        </div>
      )}
    </div>
  );
});

SystemDesignNotesEditor.displayName = "SystemDesignNotesEditor";
