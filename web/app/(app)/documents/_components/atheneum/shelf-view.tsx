"use client";

import type { ExplorerDocumentItem } from "@/lib/api/types/documents";

import { Skeleton } from "@/components/ui/skeleton";

import { ShelfCard } from "./shelf-card";

function ShelfSkeleton({ count }: { count: number }) {
 return (
 <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6">
 {Array.from({ length: count }).map((_, idx) => (
 <div key={idx} className="space-y-3">
 <Skeleton className="aspect-[3/4] w-full rounded-xl" />
 <Skeleton className="h-4 w-5/6" />
 <Skeleton className="h-3 w-3/4" />
 </div>
 ))}
 </div>
 );
}

export function ShelfView({
 items,
 loading,
 errorMessage,
 onRetry,
 onSelect,
}: {
 items: ExplorerDocumentItem[];
 loading: boolean;
 errorMessage?: string | null;
 onRetry?: () => void;
 onSelect: (id: string) => void;
}) {
 if (loading) {
 return <ShelfSkeleton count={18} />;
 }

 if (errorMessage) {
 return (
 <div className="rounded-xl border p-6">
 <p className="text-sm font-medium">Couldn’t load documents.</p>
 <p className="text-muted-foreground mt-1 text-sm">{errorMessage}</p>
 {onRetry ? (
 <button
 type="button"
 className="text-primary mt-3 text-sm underline underline-offset-4"
 onClick={onRetry}
 >
 Retry
 </button>
 ) : null}
 </div>
 );
 }

 if (!items.length) {
 return (
 <div className="text-muted-foreground rounded-xl border p-6 text-sm">
 No documents yet. Capture something, then return here.
 </div>
 );
 }

 return (
 <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6">
 {items.map((item) => (
 <ShelfCard key={item.id} item={item} onSelect={onSelect} />
 ))}
 </div>
 );
}
