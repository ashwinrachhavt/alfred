"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useMemo, useState, useSyncExternalStore } from "react";

import { safeGetItem, safeSetJSON } from "@/lib/storage";
import type { SystemDesignSession } from "@/lib/api/types/system-design";

import { useCreateSystemDesignSession } from "@/features/system-design/mutations";
import { formatErrorMessage } from "@/lib/utils";
import { useSystemDesignTemplates } from "@/features/system-design/queries";
import { SystemDesignTemplatePicker } from "@/components/system-design/system-design-template-picker";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";

type RecentSystemDesignSession = {
 id: string;
 shareId: string;
 title: string | null;
 problemStatement: string;
 createdAt: string;
};

const RECENTS_KEY = "alfred:system-design:recents:v1";
const RECENTS_EVENT = "alfred:system-design:recents-changed";
const EMPTY_RECENTS: RecentSystemDesignSession[] = [];

function safeParseRecents(raw: string | null): RecentSystemDesignSession[] {
 if (!raw) return [];
 try {
 const parsed = JSON.parse(raw) as unknown;
 return Array.isArray(parsed) ? (parsed as RecentSystemDesignSession[]) : [];
 } catch {
 return [];
 }
}

let _cachedRawRecents: string | null = null;
let _cachedParsedRecents: RecentSystemDesignSession[] = EMPTY_RECENTS;

function readRecentsSnapshot(): RecentSystemDesignSession[] {
 if (typeof window === "undefined") return [];

 const raw = safeGetItem(RECENTS_KEY);
 if (raw === _cachedRawRecents) return _cachedParsedRecents;

 _cachedRawRecents = raw;
 _cachedParsedRecents = safeParseRecents(raw) || EMPTY_RECENTS;
 return _cachedParsedRecents;
}

function subscribeToRecents(onStoreChange: () => void): () => void {
 if (typeof window === "undefined") return () => {};

 const handler = (event: Event) => {
 const storageEvent = event as StorageEvent;
 // "storage" only fires on other tabs; we also listen for a same-tab custom event.
 if (event.type === "storage" && storageEvent.key !== RECENTS_KEY) return;
 onStoreChange();
 };

 window.addEventListener("storage", handler);
 window.addEventListener(RECENTS_EVENT, handler);
 return () => {
 window.removeEventListener("storage", handler);
 window.removeEventListener(RECENTS_EVENT, handler);
 };
}

function notifyRecentsChanged(): void {
 if (typeof window === "undefined") return;
 window.dispatchEvent(new Event(RECENTS_EVENT));
}

function useRecentSystemDesignSessions(): RecentSystemDesignSession[] {
 return useSyncExternalStore(subscribeToRecents, readRecentsSnapshot, () => EMPTY_RECENTS);
}

function toRecentSession(session: SystemDesignSession): RecentSystemDesignSession {
 return {
 id: session.id,
 shareId: session.share_id,
 title: session.title ?? null,
 problemStatement: session.problem_statement,
 createdAt: session.created_at,
 };
}

type SystemDesignStartClientProps = {
 initialTitle?: string;
 initialProblemStatement?: string;
 initialTemplateId?: string;
};

export function SystemDesignStartClient({
 initialTitle = "",
 initialProblemStatement = "",
 initialTemplateId = "",
}: SystemDesignStartClientProps) {
 const router = useRouter();

 const [title, setTitle] = useState(() => initialTitle.trim());
 const [problemStatement, setProblemStatement] = useState(() => initialProblemStatement.trim());
 const [templateId, setTemplateId] = useState<string | null>(() => {
 const trimmed = initialTemplateId.trim();
 return trimmed ? trimmed : null;
 });

 const templatesQuery = useSystemDesignTemplates();
 const templates = templatesQuery.data ?? [];
 const isLoadingTemplates = templatesQuery.isPending;
 const createSession = useCreateSystemDesignSession();
 const [error, setError] = useState<string | null>(null);

 const recents = useRecentSystemDesignSessions();

 const canCreate = useMemo(
 () => problemStatement.trim().length > 0 && !createSession.isPending,
 [problemStatement, createSession.isPending],
 );

 async function onCreateSession() {
 setError(null);
 try {
 const session = await createSession.mutateAsync({
 title: title.trim() || null,
 problem_statement: problemStatement.trim(),
 template_id: templateId,
 });

 const next = [toRecentSession(session), ...recents]
 .filter((item, idx, arr) => arr.findIndex((x) => x.id === item.id) === idx)
 .slice(0, 10);
 safeSetJSON(RECENTS_KEY, next);
 notifyRecentsChanged();

 router.push(`/system-design/sessions/${session.id}`);
 } catch (err) {
 setError(formatErrorMessage(err));
 }
 }

 const errorMessage =
 error ?? (templatesQuery.error ? formatErrorMessage(templatesQuery.error) : null);

 return (
 <div className="grid gap-6 lg:grid-cols-[1fr_380px]">
 <div className="space-y-6">
 <header className="space-y-2">
 <h1 className="text-3xl font-semibold tracking-tight">System Design</h1>
 <p className="text-muted-foreground">
 Start a system design interview session with a whiteboard, AI critique, and knowledge
 capture.
 </p>
 </header>

 <Card>
 <CardHeader>
 <CardTitle>New Session</CardTitle>
 </CardHeader>
 <CardContent className="space-y-5">
 <div className="space-y-2">
 <Label htmlFor="sdTitle">Title (optional)</Label>
 <Input
 id="sdTitle"
 placeholder="e.g. Design Twitter"
 value={title}
 onChange={(e) => setTitle(e.target.value)}
 />
 </div>

 <div className="space-y-2">
 <Label htmlFor="sdProblem">Problem statement</Label>
 <Textarea
 id="sdProblem"
 placeholder="Describe the system you want to design (scale, constraints, requirements)."
 value={problemStatement}
 onChange={(e) => setProblemStatement(e.target.value)}
 rows={7}
 />
 </div>

 <div className="space-y-2">
 {isLoadingTemplates ? (
 <p className="text-muted-foreground text-xs">Loading templates…</p>
 ) : (
 <SystemDesignTemplatePicker
 templates={templates}
 selectedTemplateId={templateId}
 onSelectTemplateId={setTemplateId}
 />
 )}
 </div>

 {errorMessage ? (
 <Alert variant="destructive">
 <AlertDescription className="text-destructive">{errorMessage}</AlertDescription>
 </Alert>
 ) : null}
 </CardContent>
 <CardFooter className="flex justify-end">
 <Button onClick={onCreateSession} disabled={!canCreate}>
 {createSession.isPending ? "Creating..." : "Create session"}
 </Button>
 </CardFooter>
 </Card>
 </div>

 <div className="space-y-6">
 <Card>
 <CardHeader>
 <CardTitle>Recent Sessions</CardTitle>
 </CardHeader>
 <CardContent className="space-y-3">
 {recents.length ? (
 <ul className="space-y-3">
 {recents.map((s) => (
 <li key={s.id} className="rounded-lg border p-3">
 <div className="flex items-start justify-between gap-3">
 <div className="min-w-0 space-y-1">
 <p className="truncate font-medium">{s.title ?? "Untitled session"}</p>
 <p className="text-muted-foreground max-h-10 overflow-hidden text-xs">
 {s.problemStatement}
 </p>
 <div className="flex flex-wrap gap-2 pt-1">
 <Badge variant="secondary">id: {s.id}</Badge>
 <Badge variant="outline">share: {s.shareId}</Badge>
 </div>
 </div>
 <Button asChild variant="outline" size="sm">
 <Link href={`/system-design/sessions/${s.id}`}>Open</Link>
 </Button>
 </div>
 </li>
 ))}
 </ul>
 ) : (
 <p className="text-muted-foreground text-sm">
 No recent sessions yet. Create one to get started.
 </p>
 )}
 </CardContent>
 </Card>
 </div>
 </div>
 );
}
