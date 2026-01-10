"use client";

import { useMemo, useState } from "react";
import Link from "next/link";

import { CheckCircle2, RefreshCw, Shield, Sparkles } from "lucide-react";
import { toast } from "sonner";

import {
  enqueueDocumentConceptsBatch,
  enqueueLearningConceptsBatch,
  getDocumentConceptsBacklog,
  getLearningConceptsBacklog,
} from "@/lib/api/admin";

import type {
  AdminBatchEnqueueResponse,
  DocumentConceptsBacklogResponse,
  LearningConceptsBacklogResponse,
} from "@/lib/api/types/admin";

import { useTaskTracker } from "@/features/tasks/task-tracker-provider";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";
import { Switch } from "@/components/ui/switch";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { JsonViewer } from "@/components/ui/json-viewer";

function extractTaskId(payload: unknown): string | null {
  if (!payload || typeof payload !== "object") return null;
  const value = (payload as { task_id?: unknown }).task_id;
  return typeof value === "string" && value.trim() ? value : null;
}

export function AdminClient() {
  const { trackTask } = useTaskTracker();

  const [learningLimit, setLearningLimit] = useState(20);
  const [learningTopicId, setLearningTopicId] = useState<string>("");
  const [learningMinAgeHours, setLearningMinAgeHours] = useState(0);
  const [learningForce, setLearningForce] = useState(false);
  const [learningBacklog, setLearningBacklog] = useState<LearningConceptsBacklogResponse | null>(
    null,
  );
  const [learningEnqueue, setLearningEnqueue] = useState<AdminBatchEnqueueResponse | null>(null);
  const [learningBusy, setLearningBusy] = useState(false);

  const [docLimit, setDocLimit] = useState(20);
  const [docMinAgeHours, setDocMinAgeHours] = useState(0);
  const [docForce, setDocForce] = useState(false);
  const [docBacklog, setDocBacklog] = useState<DocumentConceptsBacklogResponse | null>(null);
  const [docEnqueue, setDocEnqueue] = useState<AdminBatchEnqueueResponse | null>(null);
  const [docBusy, setDocBusy] = useState(false);

  const topicIdNumber = useMemo(() => {
    const trimmed = learningTopicId.trim();
    if (!trimmed) return null;
    const parsed = Number(trimmed);
    return Number.isFinite(parsed) ? parsed : null;
  }, [learningTopicId]);

  async function refreshLearningBacklog() {
    setLearningBusy(true);
    try {
      const res = await getLearningConceptsBacklog({
        limit: Math.max(1, Math.min(200, learningLimit)),
        topic_id: topicIdNumber,
        min_age_hours: Math.max(0, Math.min(168, learningMinAgeHours)),
      });
      setLearningBacklog(res);
      toast.success("Loaded learning backlog.");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to load backlog.");
    } finally {
      setLearningBusy(false);
    }
  }

  async function enqueueLearning() {
    setLearningBusy(true);
    try {
      const res = await enqueueLearningConceptsBatch({
        limit: 0,
        topic_id: topicIdNumber,
        min_age_hours: Math.max(0, Math.min(168, learningMinAgeHours)),
        force: learningForce,
      });
      setLearningEnqueue(res);
      const taskId = extractTaskId(res);
      if (taskId) {
        trackTask({
          id: taskId,
          source: "admin",
          label: "Learning concepts batch",
          href: "/admin",
        });
      }
      toast.success("Batch enqueued.");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to enqueue.");
    } finally {
      setLearningBusy(false);
    }
  }

  async function refreshDocumentBacklog() {
    setDocBusy(true);
    try {
      const res = await getDocumentConceptsBacklog({
        limit: Math.max(1, Math.min(200, docLimit)),
        min_age_hours: Math.max(0, Math.min(168, docMinAgeHours)),
      });
      setDocBacklog(res);
      toast.success("Loaded document backlog.");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to load backlog.");
    } finally {
      setDocBusy(false);
    }
  }

  async function enqueueDocuments() {
    setDocBusy(true);
    try {
      const res = await enqueueDocumentConceptsBatch({
        limit: 0,
        min_age_hours: Math.max(0, Math.min(168, docMinAgeHours)),
        force: docForce,
      });
      setDocEnqueue(res);
      const taskId = extractTaskId(res);
      if (taskId) {
        trackTask({
          id: taskId,
          source: "admin",
          label: "Document concepts batch",
          href: "/admin",
        });
      }
      toast.success("Batch enqueued.");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to enqueue.");
    } finally {
      setDocBusy(false);
    }
  }

  return (
    <div className="space-y-6">
      <header className="space-y-2">
        <div className="flex items-center gap-2">
          <Shield className="text-muted-foreground h-5 w-5" aria-hidden="true" />
          <h1 className="text-3xl font-semibold tracking-tight">Admin</h1>
        </div>
        <p className="text-muted-foreground">
          Operational controls and backlogs. Enqueued actions show up in{" "}
          <Link className="text-primary underline underline-offset-2" href="/tasks">
            Tasks
          </Link>
          .
        </p>
      </header>

      <Tabs defaultValue="learning">
        <TabsList>
          <TabsTrigger value="learning">Learning concepts</TabsTrigger>
          <TabsTrigger value="documents">Document concepts</TabsTrigger>
        </TabsList>

        <TabsContent value="learning" className="mt-6 space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Backlog</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid gap-4 sm:grid-cols-3">
                <div className="space-y-2">
                  <Label htmlFor="lcLimit">Limit</Label>
                  <Input
                    id="lcLimit"
                    inputMode="numeric"
                    value={String(learningLimit)}
                    onChange={(e) => setLearningLimit(Number(e.target.value))}
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="lcTopic">Topic id (optional)</Label>
                  <Input
                    id="lcTopic"
                    value={learningTopicId}
                    onChange={(e) => setLearningTopicId(e.target.value)}
                    placeholder="e.g. 123"
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="lcAge">Min age (hours)</Label>
                  <Input
                    id="lcAge"
                    inputMode="numeric"
                    value={String(learningMinAgeHours)}
                    onChange={(e) => setLearningMinAgeHours(Number(e.target.value))}
                  />
                </div>
              </div>

              <div className="flex flex-wrap items-center gap-2">
                <Button type="button" variant="outline" onClick={() => void refreshLearningBacklog()} disabled={learningBusy}>
                  <RefreshCw className="h-4 w-4" aria-hidden="true" />
                  Refresh
                </Button>
              </div>

              {learningBacklog ? <JsonViewer value={learningBacklog} title="Backlog" /> : null}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Enqueue extraction batch</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex items-center justify-between rounded-lg border p-4">
                <div className="space-y-1">
                  <p className="text-sm font-medium">Force</p>
                  <p className="text-muted-foreground text-xs">
                    Re-run extraction even when already present.
                  </p>
                </div>
                <Switch checked={learningForce} onCheckedChange={setLearningForce} />
              </div>

              <div className="flex flex-wrap items-center gap-2">
                <Button type="button" onClick={() => void enqueueLearning()} disabled={learningBusy}>
                  <Sparkles className="h-4 w-4" aria-hidden="true" />
                  Enqueue
                </Button>
                {learningEnqueue ? (
                  <span className="text-muted-foreground flex items-center gap-1 text-xs">
                    <CheckCircle2 className="h-4 w-4" aria-hidden="true" /> queued
                  </span>
                ) : null}
              </div>

              {learningEnqueue ? (
                <>
                  <Separator />
                  <JsonViewer value={learningEnqueue} title="Enqueue response" collapsed />
                </>
              ) : null}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="documents" className="mt-6 space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Backlog</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid gap-4 sm:grid-cols-2">
                <div className="space-y-2">
                  <Label htmlFor="dcLimit">Limit</Label>
                  <Input
                    id="dcLimit"
                    inputMode="numeric"
                    value={String(docLimit)}
                    onChange={(e) => setDocLimit(Number(e.target.value))}
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="dcAge">Min age (hours)</Label>
                  <Input
                    id="dcAge"
                    inputMode="numeric"
                    value={String(docMinAgeHours)}
                    onChange={(e) => setDocMinAgeHours(Number(e.target.value))}
                  />
                </div>
              </div>

              <div className="flex flex-wrap items-center gap-2">
                <Button type="button" variant="outline" onClick={() => void refreshDocumentBacklog()} disabled={docBusy}>
                  <RefreshCw className="h-4 w-4" aria-hidden="true" />
                  Refresh
                </Button>
              </div>

              {docBacklog ? <JsonViewer value={docBacklog} title="Backlog" /> : null}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Enqueue extraction batch</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex items-center justify-between rounded-lg border p-4">
                <div className="space-y-1">
                  <p className="text-sm font-medium">Force</p>
                  <p className="text-muted-foreground text-xs">
                    Re-run extraction even when already present.
                  </p>
                </div>
                <Switch checked={docForce} onCheckedChange={setDocForce} />
              </div>

              <div className="flex flex-wrap items-center gap-2">
                <Button type="button" onClick={() => void enqueueDocuments()} disabled={docBusy}>
                  <Sparkles className="h-4 w-4" aria-hidden="true" />
                  Enqueue
                </Button>
                {docEnqueue ? (
                  <span className="text-muted-foreground flex items-center gap-1 text-xs">
                    <CheckCircle2 className="h-4 w-4" aria-hidden="true" /> queued
                  </span>
                ) : null}
              </div>

              {docEnqueue ? (
                <>
                  <Separator />
                  <JsonViewer value={docEnqueue} title="Enqueue response" collapsed />
                </>
              ) : null}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}

