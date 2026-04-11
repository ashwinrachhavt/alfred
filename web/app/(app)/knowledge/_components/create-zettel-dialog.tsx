"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import {
 Dialog,
 DialogContent,
 DialogTitle,
} from "@/components/ui/dialog";
import { VisuallyHidden } from "@radix-ui/react-visually-hidden";
import { useCreateZettel } from "@/features/zettels/mutations";
import { useIsApplePlatform } from "@/lib/hooks/use-is-apple-platform";
import { usePasteDetection } from "@/lib/hooks/use-paste-detection";
import { apiPostJson } from "@/lib/api/client";
import { apiRoutes } from "@/lib/api/routes";
import { ArrowUp, ChevronDown, ChevronUp, Loader2, Sparkles, X } from "lucide-react";

type Props = {
 open: boolean;
 onOpenChange: (open: boolean) => void;
 defaultTitle?: string;
 defaultContent?: string;
 defaultSummary?: string;
 defaultTags?: string[];
 defaultTopic?: string;
};

export function CreateZettelDialog({
 open,
 onOpenChange,
 defaultTitle = "",
 defaultContent = "",
 defaultSummary = "",
 defaultTags = [],
 defaultTopic = "",
}: Props) {
 const [content, setContent] = useState(defaultContent);
 const [title, setTitle] = useState(defaultTitle);
 const [summary, setSummary] = useState(defaultSummary);
 const [tags, setTags] = useState(defaultTags.join(", "));
 const [topic, setTopic] = useState(defaultTopic);
 const [showMeta, setShowMeta] = useState(false);
 const [isLoadingTags, setIsLoadingTags] = useState(false);
 const isApplePlatform = useIsApplePlatform();

 const textareaRef = useRef<HTMLTextAreaElement>(null);
 const createMutation = useCreateZettel();
 const { isPasteMode, tokenEstimate, handlePaste, extractTitle, reset: resetPaste } = usePasteDetection();

 // Auto-resize textarea
 const autoResize = useCallback(() => {
   const el = textareaRef.current;
   if (!el) return;
   el.style.height = "auto";
   el.style.height = `${Math.min(el.scrollHeight, window.innerHeight * 0.55)}px`;
 }, []);

 useEffect(() => {
   autoResize();
 }, [content, autoResize]);

 // Sync defaults
 useEffect(() => {
   setTitle(defaultTitle);
   setContent(defaultContent);
   setSummary(defaultSummary);
   setTags(defaultTags.join(", "));
   setTopic(defaultTopic);
   if (defaultTitle || defaultTags.length > 0 || defaultTopic) {
     setShowMeta(true);
   }
 }, [defaultTitle, defaultContent, defaultSummary, defaultTags, defaultTopic]);

 // Focus textarea on open
 useEffect(() => {
   if (open) {
     setTimeout(() => textareaRef.current?.focus(), 100);
   }
 }, [open]);

 const reset = useCallback(() => {
   setTitle(defaultTitle);
   setContent(defaultContent);
   setSummary(defaultSummary);
   setTags(defaultTags.join(", "));
   setTopic(defaultTopic);
   setShowMeta(false);
   resetPaste();
 }, [defaultTitle, defaultContent, defaultSummary, defaultTags, defaultTopic, resetPaste]);

 const handleCreate = useCallback(() => {
   const text = content.trim();
   if (!text) return;

   // Auto-extract title from first line if not manually set
   const finalTitle = title.trim() || extractTitle(text) || "Untitled";

   const tagList = tags
     .split(",")
     .map((t) => t.trim().toLowerCase())
     .filter(Boolean);

   createMutation.mutate(
     {
       title: finalTitle,
       content: text,
       summary: summary.trim() || undefined,
       tags: tagList.length > 0 ? tagList : undefined,
       topic: topic.trim() || undefined,
       importance: 5,
       confidence: 0.5,
     },
     {
       onSuccess: () => {
         reset();
         onOpenChange(false);
       },
     },
   );
 }, [title, content, summary, tags, topic, createMutation, reset, onOpenChange, extractTitle]);

 const handleContentPaste = useCallback((e: React.ClipboardEvent<HTMLTextAreaElement>) => {
   handlePaste(e);
   const text = e.clipboardData.getData("text/plain");
   if (text.length > 100 && !title.trim()) {
     const autoTitle = extractTitle(text);
     if (autoTitle) setTitle(autoTitle);
   }
 }, [handlePaste, extractTitle, title]);

 const handleAutoTag = useCallback(async () => {
   if (!content.trim()) return;
   setIsLoadingTags(true);
   try {
     const response = await apiPostJson<{ tags: string[] }, { text: string }>(
       apiRoutes.zettels.suggestTags,
       { text: content.trim().slice(0, 5000) }
     );
     if (response.tags?.length) {
       setTags(response.tags.join(", "));
       setShowMeta(true);
     }
   } catch { /* silent */ } finally {
     setIsLoadingTags(false);
   }
 }, [content]);

 const handleKeyDown = useCallback((e: React.KeyboardEvent<HTMLTextAreaElement>) => {
   // Cmd/Ctrl+Enter submits
   if ((e.metaKey || e.ctrlKey) && e.key === "Enter") {
     e.preventDefault();
     handleCreate();
   }
 }, [handleCreate]);

 const canSubmit = content.trim().length > 0 && !createMutation.isPending;

 return (
   <Dialog open={open} onOpenChange={onOpenChange}>
     <DialogContent className="sm:max-w-[680px] p-0 gap-0 overflow-hidden">
       <VisuallyHidden><DialogTitle>Create new zettel</DialogTitle></VisuallyHidden>
       {/* Header — minimal */}
       <div className="flex items-center justify-between px-5 pt-4 pb-2">
         <span className="text-sm font-medium text-muted-foreground">New Zettel</span>
         <div className="flex items-center gap-2">
           {tokenEstimate > 0 && (
             <span className="text-[10px] text-muted-foreground tabular-nums">
               ~{tokenEstimate.toLocaleString()} tokens
             </span>
           )}
           <button onClick={() => onOpenChange(false)} className="text-muted-foreground hover:text-foreground transition-colors">
             <X className="size-4" />
           </button>
         </div>
       </div>

       {/* Main input — Claude-style */}
       <div className="px-5 pb-3">
         <div className="relative rounded-xl border bg-card focus-within:ring-1 focus-within:ring-primary/50 transition-all">
           {/* Auto-extracted title pill */}
           {title && (
             <div className="px-4 pt-3 pb-1">
               <input
                 value={title}
                 onChange={(e) => setTitle(e.target.value)}
                 className="w-full bg-transparent text-[15px] font-semibold outline-none placeholder:text-muted-foreground/50"
                 placeholder="Title"
               />
             </div>
           )}

           {/* Textarea — the hero */}
           <textarea
             ref={textareaRef}
             value={content}
             onChange={(e) => {
               setContent(e.target.value);
             }}
             onPaste={handleContentPaste}
             onKeyDown={handleKeyDown}
             placeholder="Paste anything, write a thought, capture an idea..."
             className={`w-full resize-none bg-transparent outline-none text-[14px] leading-relaxed placeholder:text-muted-foreground/40 ${
               title ? "px-4 pt-1 pb-3" : "px-4 py-3"
             }`}
             style={{ minHeight: "120px", maxHeight: "55vh" }}
             rows={3}
           />

           {/* Bottom bar inside the input — like Claude's toolbar */}
           <div className="flex items-center justify-between px-3 pb-2.5 pt-1">
             <div className="flex items-center gap-1.5">
               {/* Meta toggle */}
               <button
                 onClick={() => setShowMeta(!showMeta)}
                 className="flex items-center gap-1 rounded-md px-2 py-1 text-[11px] text-muted-foreground hover:bg-muted hover:text-foreground transition-colors"
               >
                 {showMeta ? <ChevronUp className="size-3" /> : <ChevronDown className="size-3" />}
                 Details
               </button>

               {/* Auto-tag */}
               <button
                 onClick={handleAutoTag}
                 disabled={!content.trim() || isLoadingTags}
                 className="flex items-center gap-1 rounded-md px-2 py-1 text-[11px] text-muted-foreground hover:bg-muted hover:text-foreground transition-colors disabled:opacity-30"
               >
                 {isLoadingTags ? <Loader2 className="size-3 animate-spin" /> : <Sparkles className="size-3" />}
                 Auto-tag
               </button>
             </div>

             {/* Submit button — like Claude's send */}
             <button
               onClick={handleCreate}
               disabled={!canSubmit}
               className="flex items-center justify-center size-8 rounded-lg bg-primary text-primary-foreground hover:bg-primary/90 transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
             >
               {createMutation.isPending ? (
                 <Loader2 className="size-4 animate-spin" />
               ) : (
                 <ArrowUp className="size-4" />
               )}
             </button>
           </div>
         </div>

         {/* Meta fields — collapsible, like Claude's model picker area */}
         {showMeta && (
           <div className="mt-3 space-y-2.5 animate-in slide-in-from-top-2 duration-200">
             {!title && (
               <input
                 value={title}
                 onChange={(e) => setTitle(e.target.value)}
                 placeholder="Title (auto-extracted from first line)"
                 className="w-full rounded-lg border bg-card px-3 py-2 text-[13px] outline-none focus:ring-1 focus:ring-primary/50 placeholder:text-muted-foreground/40"
               />
             )}
             <input
               value={summary}
               onChange={(e) => setSummary(e.target.value)}
               placeholder="Summary — one-sentence distillation"
               className="w-full rounded-lg border bg-card px-3 py-2 text-[13px] outline-none focus:ring-1 focus:ring-primary/50 placeholder:text-muted-foreground/40"
             />
             <div className="flex gap-2">
               <input
                 value={topic}
                 onChange={(e) => setTopic(e.target.value)}
                 placeholder="Topic"
                 className="flex-1 rounded-lg border bg-card px-3 py-2 text-[13px] outline-none focus:ring-1 focus:ring-primary/50 placeholder:text-muted-foreground/40"
               />
               <input
                 value={tags}
                 onChange={(e) => setTags(e.target.value)}
                 placeholder="Tags (comma-separated)"
                 className="flex-1 rounded-lg border bg-card px-3 py-2 text-[13px] outline-none focus:ring-1 focus:ring-primary/50 placeholder:text-muted-foreground/40"
               />
             </div>
           </div>
         )}

         {/* Hint */}
         <div className="flex items-center justify-between mt-2.5 px-1">
           <span className="text-[10px] text-muted-foreground/50">
             {isPasteMode ? "Title auto-extracted" : "Paste text or type freely"}
           </span>
           <span className="text-[10px] text-muted-foreground/50">
             {isApplePlatform ? "⌘" : "Ctrl"}+Enter to create
           </span>
         </div>
       </div>
     </DialogContent>
   </Dialog>
 );
}
