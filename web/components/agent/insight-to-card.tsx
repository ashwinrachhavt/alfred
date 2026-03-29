"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { BookmarkPlus, Loader2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { apiFetch } from "@/lib/api/client";
import { apiRoutes } from "@/lib/api/routes";

/**
 * Floating "Save as Card" button that appears when text is selected
 * inside an assistant message. Creates a zettel from the selected text.
 *
 * Usage: Wrap assistant message content with <InsightToCard threadTopics={[...]}>
 */
export function InsightToCard({
 children,
 threadTopics = [],
}: {
 children: React.ReactNode;
 threadTopics?: string[];
}) {
 const containerRef = useRef<HTMLDivElement>(null);
 const [selection, setSelection] = useState<{ text: string; rect: DOMRect } | null>(null);
 const [saving, setSaving] = useState(false);

 const handleMouseUp = useCallback(() => {
 const sel = window.getSelection();
 if (!sel || sel.isCollapsed || !containerRef.current) {
 setSelection(null);
 return;
 }

 // Only capture selections within this container
 const range = sel.getRangeAt(0);
 if (!containerRef.current.contains(range.commonAncestorContainer)) {
 setSelection(null);
 return;
 }

 const text = sel.toString().trim();
 if (text.length < 10) {
 setSelection(null);
 return;
 }

 const rect = range.getBoundingClientRect();
 setSelection({ text, rect });
 }, []);

 const handleSaveAsCard = async () => {
 if (!selection) return;
 setSaving(true);

 try {
 const title = selection.text.slice(0, 60).replace(/\n/g, " ");
 await apiFetch(apiRoutes.zettels.cards, {
 method: "POST",
 body: JSON.stringify({
 title,
 content: selection.text,
 tags: threadTopics.slice(0, 5),
 topic: threadTopics[0] || null,
 }),
 });
 setSelection(null);
 window.getSelection()?.removeAllRanges();
 } catch {
 // TODO: error toast
 } finally {
 setSaving(false);
 }
 };

 // Dismiss on click outside
 useEffect(() => {
 const handler = () => {
 const sel = window.getSelection();
 if (!sel || sel.isCollapsed) {
 setSelection(null);
 }
 };

 document.addEventListener("mousedown", handler);
 return () => document.removeEventListener("mousedown", handler);
 }, []);

 return (
 <div ref={containerRef} onMouseUp={handleMouseUp} className="relative">
 {children}

 {selection && (
 <div
 className="fixed z-50"
 style={{
 top: selection.rect.top - 40,
 left: selection.rect.left + selection.rect.width / 2 - 60,
 }}
 >
 <Button
 size="sm"
 variant="default"
 onClick={handleSaveAsCard}
 disabled={saving}
 className="bg-[var(--accent)] hover:bg-[var(--accent-hover)] text-white shadow-lg text-xs gap-1.5"
 >
 {saving ? (
 <Loader2 className="h-3 w-3 animate-spin" />
 ) : (
 <BookmarkPlus className="h-3 w-3" />
 )}
 Save as Card
 </Button>
 </div>
 )}
 </div>
 );
}
