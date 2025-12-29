"use client";

// import { useEditor, EditorContent, BubbleMenu, FloatingMenu } from "@tiptap/react";
import { useEditor, EditorContent } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import Placeholder from "@tiptap/extension-placeholder";
import { Markdown } from "@tiptap/markdown";
import Typography from "@tiptap/extension-typography";
import {
  forwardRef,
  useEffect,
  useImperativeHandle,
  useMemo,
  useRef,
  useState,
} from "react";
import { cn } from "@/lib/utils";
/*
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
} from "lucide-react";
import { Separator } from "@/components/ui/separator";
*/

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
    },
    onFocus: () => setIsFocused(true),
    onBlur: () => setIsFocused(false),
  });

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
      {/* Floating Menu for empty lines */}
      {/*
      {editor && (
        <FloatingMenu editor={editor} tippyOptions={{ duration: 100 }} className="flex items-center gap-1 rounded-md border bg-popover p-1 shadow-md">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => editor.chain().focus().toggleHeading({ level: 1 }).run()}
            className={cn("h-8 w-8 p-0", editor.isActive("heading", { level: 1 }) && "bg-accent")}
          >
            <Heading1 className="h-4 w-4" />
          </Button>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => editor.chain().focus().toggleHeading({ level: 2 }).run()}
            className={cn("h-8 w-8 p-0", editor.isActive("heading", { level: 2 }) && "bg-accent")}
          >
            <Heading2 className="h-4 w-4" />
          </Button>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => editor.chain().focus().toggleBulletList().run()}
            className={cn("h-8 w-8 p-0", editor.isActive("bulletList") && "bg-accent")}
          >
            <List className="h-4 w-4" />
          </Button>
        </FloatingMenu>
      )}
      */}

      {/* Bubble Menu for selections */}
      {/*
      {editor && (
        <BubbleMenu editor={editor} tippyOptions={{ duration: 100 }} className="flex items-center gap-1 rounded-md border bg-popover p-1 shadow-md">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => editor.chain().focus().toggleBold().run()}
            className={cn("h-8 w-8 p-0", editor.isActive("bold") && "bg-accent text-accent-foreground")}
          >
            <Bold className="h-4 w-4" />
          </Button>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => editor.chain().focus().toggleItalic().run()}
            className={cn("h-8 w-8 p-0", editor.isActive("italic") && "bg-accent text-accent-foreground")}
          >
            <Italic className="h-4 w-4" />
          </Button>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => editor.chain().focus().toggleStrike().run()}
            className={cn("h-8 w-8 p-0", editor.isActive("strike") && "bg-accent text-accent-foreground")}
          >
            <Strikethrough className="h-4 w-4" />
          </Button>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => editor.chain().focus().toggleCode().run()}
            className={cn("h-8 w-8 p-0", editor.isActive("code") && "bg-accent text-accent-foreground")}
          >
            <Code className="h-4 w-4" />
          </Button>
          <Separator orientation="vertical" className="mx-1 h-6" />
          <Button
            variant="ghost"
            size="sm"
            className="h-8 gap-1.5 px-2 text-xs font-medium text-pink-600 hover:bg-pink-50 hover:text-pink-700 dark:text-pink-400 dark:hover:bg-pink-950/30"
            onClick={() => {
              // Placeholder for AI action
              alert("AI Assist feature coming soon!");
            }}
          >
            <Sparkles className="h-3.5 w-3.5" />
            AI Check
          </Button>
        </BubbleMenu>
      )}
      */}

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
