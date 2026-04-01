"use client";

import { useEffect, useState } from "react";

import { BookOpen, ExternalLink, Loader2, Plus, Sparkles, X } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { useDocumentDetails } from "@/features/documents/queries";
import { useEnrichDocument, useFetchAndOrganize } from "@/features/documents/mutations";
import { useZettelsByDocument } from "@/features/zettels/queries";
import { CreateZettelDialog } from "@/app/(app)/knowledge/_components/create-zettel-dialog";
import { ReaderMode } from "./reader-mode";

type Props = {
 docId: string;
 onClose: () => void;
};

export function InboxDetail({ docId, onClose }: Props) {
 const { data, isLoading, refetch } = useDocumentDetails(docId);
 const enrichMutation = useEnrichDocument(docId);
 const fetchMutation = useFetchAndOrganize(docId);
 const [enrichStatus, setEnrichStatus] = useState<"idle" | "fetching" | "enriching" | "done">("idle");
 const [readerOpen, setReaderOpen] = useState(false);

 useEffect(() => {
 const handler = (e: KeyboardEvent) => {
 if (e.key === "Escape") onClose();
 };
 window.addEventListener("keydown", handler);
 return () => window.removeEventListener("keydown", handler);
 }, [onClose]);

 const contentIsShort = (data?.cleaned_text?.length ?? 0) < 500;
 const hasSourceUrl = Boolean(data?.source_url && !data.source_url.startsWith("about:"));

 const handleEnrich = async () => {
 try {
 // If content is too short and we have a source URL, fetch full text first
 if (contentIsShort && hasSourceUrl) {
 setEnrichStatus("fetching");
 await fetchMutation.mutateAsync(true);
 // Poll for completion
 let attempts = 0;
 const poll = setInterval(async () => {
 attempts++;
 const result = await refetch();
 const newLen = result.data?.cleaned_text?.length ?? 0;
 if (newLen > 500 || result.data?.enrichment || result.data?.summary || attempts >= 15) {
 clearInterval(poll);
 setEnrichStatus("done");
 }
 }, 5000);
 } else {
 // Content is long enough — just enrich
 setEnrichStatus("enriching");
 await enrichMutation.mutateAsync(true);
 let attempts = 0;
 const poll = setInterval(async () => {
 attempts++;
 const result = await refetch();
 if (result.data?.enrichment || result.data?.summary || attempts >= 12) {
 clearInterval(poll);
 setEnrichStatus("done");
 }
 }, 5000);
 }
 } catch {
 setEnrichStatus("idle");
 }
 };

 const hasEnrichment = Boolean(data?.summary || data?.enrichment);
 const summary = data?.summary as { short?: string; long?: string } | null;
 const topics = data?.topics as { primary?: string; secondary?: string[] } | null;

 return (
 <>
 {/* Backdrop */}
 <div className="fixed inset-0 z-40 bg-black/20 backdrop-blur-[2px]" onClick={onClose} />

 {/* Panel */}
 <div className="fixed inset-y-0 right-0 z-50 flex w-[55vw] max-w-2xl flex-col border-l bg-background shadow-2xl animate-in slide-in-from-right duration-200">
 <div className="flex items-center justify-between border-b px-5 py-3">
 <div className="flex items-center gap-3 min-w-0">
 <h2 className="truncate text-sm font-semibold">{data?.title ?? "Document"}</h2>
 {data?.content_type && (
 <Badge variant="secondary" className="shrink-0 text-[10px]">{data.content_type}</Badge>
 )}
 </div>
 <div className="flex items-center gap-1">
 {data && !hasEnrichment && enrichStatus === "idle" && (
 <Button
 variant="outline"
 size="sm"
 className="h-7 gap-1.5 font-medium text-[10px] uppercase tracking-wide text-[var(--alfred-accent)]"
 onClick={handleEnrich}
 >
 <Sparkles className="size-3" />
 {contentIsShort && hasSourceUrl ? "Fetch & Organize" : "Enrich & Organize"}
 </Button>
 )}
 {/* Re-fetch button for already enriched docs with short content */}
 {data && hasEnrichment && contentIsShort && hasSourceUrl && enrichStatus === "idle" && (
 <Button
 variant="ghost"
 size="sm"
 className="h-7 gap-1.5 font-medium text-[10px] uppercase tracking-wide text-muted-foreground"
 onClick={handleEnrich}
 >
 <Sparkles className="size-3" />
 Fetch Full Text
 </Button>
 )}
 {enrichStatus === "fetching" && (
 <span className="flex items-center gap-1.5 text-[10px] text-muted-foreground">
 <Loader2 className="size-3 animate-spin" />
 Fetching full article...
 </span>
 )}
 {enrichStatus === "enriching" && (
 <span className="flex items-center gap-1.5 text-[10px] text-muted-foreground">
 <Loader2 className="size-3 animate-spin" />
 Enriching...
 </span>
 )}
 {enrichStatus === "done" && (
 <span className="text-[10px] text-green-600">Organized ✓</span>
 )}
		 {data?.cleaned_text && (
			<button
			 onClick={() => setReaderOpen(true)}
			 className="text-xs font-medium tracking-wide text-primary hover:underline"
			>
			 Read
			</button>
		 )}
 {data?.source_url && (
 <Button variant="ghost" size="icon" className="size-7" asChild>
 <a href={data.source_url} target="_blank" rel="noopener noreferrer" title="Open source">
 <ExternalLink className="size-3.5" />
 </a>
 </Button>
 )}
 <Button variant="ghost" size="icon" className="size-7" onClick={onClose}>
 <X className="size-4" />
 </Button>
 </div>
 </div>
 <div className="flex-1 overflow-y-auto p-6">
 {isLoading ? (
 <div className="space-y-4">
 <Skeleton className="h-8 w-3/4" />
 <Skeleton className="h-4 w-full" />
 <Skeleton className="h-4 w-full" />
 <Skeleton className="h-4 w-5/6" />
 <Skeleton className="h-4 w-full" />
 <Skeleton className="h-4 w-2/3" />
 </div>
 ) : data ? (
 <article className="prose prose-sm dark:prose-invert max-w-none">
 {data.source_url && (
 <p className="text-muted-foreground not-prose mb-4 flex items-center gap-2 text-xs ">
 <span className="truncate">{data.source_url}</span>
 </p>
 )}

 {/* Enriched view: structured markdown template */}
 {hasEnrichment ? (
 <div className="space-y-6">
 {/* Title */}
 <h1 className="text-2xl leading-tight">{data.title}</h1>

 {/* Topics */}
 {topics && (
 <div className="not-prose flex flex-wrap gap-1.5">
 {topics.primary && (
 <Badge className="bg-[var(--alfred-accent)] text-white text-[10px] uppercase">
 {topics.primary.replace(/_/g, " ")}
 </Badge>
 )}
 {topics.secondary?.map((t, i) => (
 <Badge key={i} variant="outline" className="text-[10px] ">
 {String(t).replace(/_/g, " ")}
 </Badge>
 ))}
 </div>
 )}

 {/* Summary */}
 {summary?.short && (
 <div className="rounded-md border border-[var(--alfred-ruled-line)] bg-muted/30 p-4">
 <p className="font-medium text-[10px] uppercase tracking-wide text-muted-foreground mb-2">
 Summary
 </p>
 <p className="text-sm leading-relaxed">{summary.short}</p>
 </div>
 )}

 {/* Long summary / analysis */}
 {summary?.long && (
 <div>
 <p className="font-medium text-[10px] uppercase tracking-wide text-muted-foreground mb-2">
 Analysis
 </p>
 <div className="whitespace-pre-wrap text-sm leading-relaxed">
 {summary.long}
 </div>
 </div>
 )}

 {/* Full text — shown as markdown if substantial */}
 {data.cleaned_text && data.cleaned_text.length > 500 ? (
 <div>
 <p className="font-medium text-[10px] uppercase tracking-wide text-muted-foreground mb-2">
 Full Text ({data.tokens ?? Math.round(data.cleaned_text.length / 4)} tokens)
 </p>
 <div className="whitespace-pre-wrap text-sm leading-relaxed">
 {data.raw_markdown || data.cleaned_text}
 </div>
 </div>
 ) : (
 <details className="group">
 <summary className="cursor-pointer font-medium text-[10px] uppercase tracking-wide text-muted-foreground hover:text-foreground">
 Original Content ({data.tokens ?? "?"} tokens)
 </summary>
 <div className="mt-3 whitespace-pre-wrap text-sm leading-relaxed text-muted-foreground">
 {data.cleaned_text}
 </div>
 </details>
 )}
 </div>
 ) : (
 /* Raw view: pre-enrichment */
 <div>
 <div className="whitespace-pre-wrap leading-relaxed">{data.cleaned_text}</div>
 {!hasEnrichment && data.cleaned_text && (
 <div className="not-prose mt-8 rounded-md border border-dashed border-muted-foreground/30 p-6 text-center">
 <Sparkles className="mx-auto mb-2 size-5 text-muted-foreground" />
 <p className="text-sm text-muted-foreground">
 This document hasn&apos;t been enriched yet.
 </p>
 <p className="text-xs text-muted-foreground/60 mt-1">
 Click &quot;Enrich &amp; Organize&quot; to generate a summary, extract topics, and structure the content.
 </p>
 </div>
 )}
 </div>
 )}
 {/* Zettel Bridge — show existing + create new */}
 <ZettelBridge docId={docId} data={data} />
 </article>
 ) : (
 <p className="text-muted-foreground">Document not found.</p>
 )}
 </div>
 </div>

		 <ReaderMode
		 isOpen={readerOpen}
		 onClose={() => setReaderOpen(false)}
		 title={data?.title || ""}
		 sourceUrl={data?.source_url}
		 summary={summary || undefined}
		 content={data?.cleaned_text || data?.raw_markdown || ""}
		 />
 </>
 );
}

// --- Zettel Bridge: shows zettels created from this document + create new ---

function ZettelBridge({ docId, data }: { docId: string; data: Record<string, unknown> }) {
 const { data: zettels = [], isLoading: zettelsLoading } = useZettelsByDocument(docId);
 const [dialogOpen, setDialogOpen] = useState(false);

 const topics = data?.topics as { primary?: string; secondary?: string[] } | null;
 const summary = data?.summary as { short?: string } | null;
 const hasEnrichment = Boolean(summary?.short || data?.enrichment);

 // Prepare default values for the dialog
 const defaultTitle = String(data?.title || "");
 const defaultContent = summary?.short || String(data?.cleaned_text || "").slice(0, 500);
 const defaultSummary = summary?.short || "";
 const defaultTags = topics?.secondary?.slice(0, 5).map((t) => String(t).toLowerCase().replace(/_/g, "-")) || [];
 const defaultTopic = topics?.primary?.replace(/_/g, "-") || "";

 return (
 <>
 <div className="not-prose mt-8 rounded-lg border border-[var(--alfred-ruled-line)] p-4">
 <div className="flex items-center justify-between mb-3">
 <div className="flex items-center gap-2">
 <BookOpen className="size-4 text-primary" />
 <span className="font-medium text-[10px] uppercase tracking-widest text-[var(--alfred-text-tertiary)]">
 Knowledge Cards
 </span>
 {zettels.length > 0 && (
 <Badge variant="secondary" className="ml-1 h-4 px-1.5 text-[9px]">
 {zettels.length}
 </Badge>
 )}
 </div>
 {hasEnrichment && (
 <Button
 size="sm"
 variant="outline"
 className="h-7 gap-1.5 text-xs font-medium tracking-wide"
 onClick={() => setDialogOpen(true)}
 >
 <Plus className="size-3" />
 Create More
 </Button>
 )}
 </div>

 {zettelsLoading ? (
 <div className="space-y-2">
 <Skeleton className="h-8 w-full" />
 <Skeleton className="h-8 w-3/4" />
 </div>
 ) : zettels.length > 0 ? (
 <div className="space-y-2">
 {zettels.map((z) => (
 <a
 key={z.id}
 href={`/knowledge?selected=${z.id}`}
 className="flex items-center gap-3 rounded-md border px-3 py-2 text-sm transition-colors hover:bg-[var(--alfred-accent-subtle)] hover:border-primary/30"
 >
 <span className="size-2 rounded-full bg-primary shrink-0" />
 <span className="text-[13px] truncate">{z.title}</span>
 {z.tags && z.tags.length > 0 && (
 <span className="ml-auto text-[9px] uppercase text-[var(--alfred-text-tertiary)] shrink-0">
 {z.tags[0]}
 </span>
 )}
 </a>
 ))}
 </div>
 ) : hasEnrichment ? (
 <p className="text-[13px] text-muted-foreground">
 No zettels created from this document yet. Click &quot;Create More&quot; to extract key concepts.
 </p>
 ) : (
 <p className="text-[13px] text-muted-foreground">
 Enrich this document first to create knowledge cards from it.
 </p>
 )}
 </div>

 <CreateZettelDialog
 open={dialogOpen}
 onOpenChange={setDialogOpen}
 defaultTitle={defaultTitle}
 defaultContent={defaultContent}
 defaultSummary={defaultSummary}
 defaultTags={defaultTags}
 defaultTopic={defaultTopic}
 />
 </>
 );
}
