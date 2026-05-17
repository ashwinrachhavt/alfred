"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";

import { BookOpen, ExternalLink, ImageIcon, Layers3, Loader2, Plus, Sparkles, X } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { useDocumentDetails } from "@/features/documents/queries";
import { useEnrichDocument, useFetchAndOrganize } from "@/features/documents/mutations";
import { useZettelsByDocument } from "@/features/zettels/queries";
import { useCreateSession } from "@/features/workspace/mutations";
import type { SourceAnalysis, SourceCapture, SourceCaptureImage } from "@/lib/api/types/documents";
import { DocumentChatThread } from "./document-chat-thread";
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
 const sourceCapture = data?.metadata?.source_capture;
 const sourceAnalysis = data?.enrichment?.source_analysis;
 const readableText = data?.cleaned_text || data?.raw_markdown || "";

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

 <SourceCaptureOverview
 sourceCapture={sourceCapture}
 sourceAnalysis={sourceAnalysis}
 fallbackCoverUrl={data.cover_image_url}
 />

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
 {readableText}
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
 <DocumentChatThread docId={docId} title={data.title} />
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

function imageSrc(image: SourceCaptureImage): string | null {
 const src = image.local_url || image.url;
 return typeof src === "string" && src.trim() ? src : null;
}

function sourceLabel(value: string | null | undefined): string {
 return String(value || "").replace(/_/g, " ");
}

function SourceCaptureOverview({
 sourceCapture,
 sourceAnalysis,
 fallbackCoverUrl,
}: {
 sourceCapture?: SourceCapture;
 sourceAnalysis?: SourceAnalysis;
 fallbackCoverUrl?: string | null;
}) {
 const images = useMemo(() => {
 const seen = new Set<string>();
 return (sourceCapture?.images || [])
 .map((image) => ({ ...image, src: imageSrc(image) }))
 .filter((image): image is SourceCaptureImage & { src: string } => {
 if (!image.src || seen.has(image.src)) return false;
 seen.add(image.src);
 return true;
 })
 .slice(0, 6);
 }, [sourceCapture?.images]);

 const coverUrl = sourceCapture?.cover_image_url || fallbackCoverUrl || images[0]?.src || null;
 const headings = sourceCapture?.headings?.slice(0, 8) || [];
 const argumentFlow = sourceAnalysis?.argument_flow?.slice(0, 4) || [];
 const showOverview = Boolean(
 sourceCapture || sourceAnalysis || coverUrl || images.length,
 );

 if (!showOverview) return null;

 return (
 <div className="not-prose mb-6 space-y-4 border-y border-[var(--alfred-ruled-line)] py-4">
 <div className="flex flex-wrap items-center gap-2">
 {sourceCapture?.kind && (
 <Badge variant="secondary" className="h-5 rounded-sm text-[9px] uppercase tracking-wide">
 {sourceLabel(sourceCapture.kind)}
 </Badge>
 )}
 {sourceCapture?.platform && (
 <Badge variant="outline" className="h-5 rounded-sm text-[9px] uppercase tracking-wide">
 {sourceLabel(sourceCapture.platform)}
 </Badge>
 )}
 {sourceCapture?.author && (
 <span className="text-[11px] text-muted-foreground">By {sourceCapture.author}</span>
 )}
 {sourceCapture?.published_at && (
 <span className="text-[11px] text-muted-foreground">{sourceCapture.published_at.slice(0, 10)}</span>
 )}
 </div>

 {coverUrl && (
 <div className="overflow-hidden rounded-md border border-[var(--alfred-ruled-line)] bg-muted/20">
 {/* Captured sources can come from arbitrary domains or local asset routes. */}
 {/* eslint-disable-next-line @next/next/no-img-element */}
 <img src={coverUrl} alt={sourceCapture?.title || "Captured source"} className="max-h-64 w-full object-cover" />
 </div>
 )}

 {sourceAnalysis?.thesis && (
 <div>
 <p className="mb-1 text-[10px] font-medium uppercase tracking-widest text-[var(--alfred-text-tertiary)]">
 Thesis
 </p>
 <p className="text-sm leading-relaxed text-foreground">{sourceAnalysis.thesis}</p>
 </div>
 )}

 <div className="grid gap-4 md:grid-cols-2">
 {headings.length > 0 && (
 <div>
 <div className="mb-2 flex items-center gap-2">
 <Layers3 className="size-3.5 text-[var(--alfred-accent)]" />
 <p className="text-[10px] font-medium uppercase tracking-widest text-[var(--alfred-text-tertiary)]">
 Structure
 </p>
 </div>
 <ol className="space-y-1 border-l border-[var(--alfred-ruled-line)] pl-3">
 {headings.map((heading, index) => (
 <li key={`${heading.text}-${index}`} className="text-[12px] leading-snug text-muted-foreground">
 {heading.text}
 </li>
 ))}
 </ol>
 </div>
 )}

 {images.length > 0 && (
 <div>
 <div className="mb-2 flex items-center gap-2">
 <ImageIcon className="size-3.5 text-[var(--alfred-accent)]" />
 <p className="text-[10px] font-medium uppercase tracking-widest text-[var(--alfred-text-tertiary)]">
 Captured Assets
 </p>
 </div>
 <div className="grid grid-cols-3 gap-2">
 {images.map((image) => (
 <div key={image.src} className="aspect-[4/3] overflow-hidden rounded border border-[var(--alfred-ruled-line)] bg-muted/20">
 {/* eslint-disable-next-line @next/next/no-img-element */}
 <img src={image.src} alt={image.alt || "Captured asset"} className="size-full object-cover" />
 </div>
 ))}
 </div>
 </div>
 )}
 </div>

 {argumentFlow.length > 0 && (
 <div>
 <p className="mb-2 text-[10px] font-medium uppercase tracking-widest text-[var(--alfred-text-tertiary)]">
 Argument Flow
 </p>
 <div className="space-y-1">
 {argumentFlow.map((item, index) => (
 <p key={`${item}-${index}`} className="text-[12px] leading-relaxed text-muted-foreground">
 {index + 1}. {item}
 </p>
 ))}
 </div>
 </div>
 )}
 </div>
 );
}

// --- Zettel Bridge: shows zettels created from this document + create new ---

function ZettelBridge({ docId, data }: { docId: string; data: Record<string, unknown> }) {
 const { data: zettels = [], isLoading: zettelsLoading } = useZettelsByDocument(docId);
 const router = useRouter();
 const createSession = useCreateSession();

 const topics = data?.topics as { primary?: string; secondary?: string[] } | null;
 const summary = data?.summary as { short?: string } | null;
 const hasEnrichment = Boolean(summary?.short || data?.enrichment);

 const seedTitle = String(data?.title || "");
 const seedContent = summary?.short || String(data?.cleaned_text || "").slice(0, 500);
 const seedTags = topics?.secondary?.slice(0, 5).map((t) => String(t).toLowerCase().replace(/_/g, "-")) || [];
 const seedTopic = topics?.primary?.replace(/_/g, "-") || "";

 const handleCreateFromDoc = async () => {
 try {
 const session = await createSession.mutateAsync({
 title: seedTitle || undefined,
 shared_topic: seedTopic || undefined,
 shared_tags: seedTags.length ? seedTags : undefined,
 source_context: docId,
 });
 // Hand off the seed draft content via sessionStorage so the workspace
 // can hydrate its first draft without polluting the URL.
 if (typeof window !== "undefined") {
 window.sessionStorage.setItem(
 `workspace.seedForSession:${session.id}`,
 JSON.stringify({ title: seedTitle, content: seedContent }),
 );
 }
 router.push(`/knowledge/session/${session.id}`);
 } catch (err) {
 toast.error("Could not start sitting", {
 description: err instanceof Error ? err.message : String(err),
 });
 }
 };

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
 onClick={handleCreateFromDoc}
 disabled={createSession.isPending}
 >
 {createSession.isPending ? (
 <Loader2 className="size-3 animate-spin" />
 ) : (
 <Plus className="size-3" />
 )}
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
 </>
 );
}
