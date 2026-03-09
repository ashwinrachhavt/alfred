"use client";

import type {
  DiagramAnalysis,
  DiagramEvaluation,
  DiagramQuestion,
  DiagramSuggestion,
  SystemDesignKnowledgeDraft,
  SystemDesignPublishResponse,
} from "@/lib/api/types/system-design";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";
import { Switch } from "@/components/ui/switch";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

export interface SessionCoachPanelProps {
  actionError: string | null;
  isActionRunning: boolean;
  autosaveState: string;

  analysis: DiagramAnalysis | null;
  questions: DiagramQuestion[] | null;
  suggestions: DiagramSuggestion[];
  evaluation: DiagramEvaluation | null;
  knowledgeDraft: SystemDesignKnowledgeDraft | null;

  publishLearningTopics: boolean;
  publishZettels: boolean;
  topicTitle: string;
  publishResult: SystemDesignPublishResponse | null;

  onPublishLearningTopicsChange: (checked: boolean) => void;
  onPublishZettelsChange: (checked: boolean) => void;
  onTopicTitleChange: (value: string) => void;

  onFlushAutosave: () => void;
  onAnalyze: () => void;
  onQuestions: () => void;
  onSuggestions: () => void;
  onEvaluate: () => void;
  onGenerateDraft: () => void;
  onPublish: () => void;
}

export function SessionCoachPanel({
  actionError,
  isActionRunning,
  autosaveState,
  analysis,
  questions,
  suggestions,
  evaluation,
  knowledgeDraft,
  publishLearningTopics,
  publishZettels,
  topicTitle,
  publishResult,
  onPublishLearningTopicsChange,
  onPublishZettelsChange,
  onTopicTitleChange,
  onFlushAutosave,
  onAnalyze,
  onQuestions,
  onSuggestions,
  onEvaluate,
  onGenerateDraft,
  onPublish,
}: SessionCoachPanelProps) {
  return (
    <Card className="flex min-h-0 flex-col">
      <CardHeader className="space-y-2">
        <CardTitle className="flex items-center justify-between">
          <span>Coach</span>
          <Button
            variant="outline"
            size="sm"
            onClick={onFlushAutosave}
            disabled={autosaveState === "saving"}
          >
            Save diagram
          </Button>
        </CardTitle>
        {actionError ? (
          <Alert variant="destructive">
            <AlertDescription className="text-destructive">{actionError}</AlertDescription>
          </Alert>
        ) : null}
      </CardHeader>

      <CardContent className="min-h-0 flex-1 overflow-auto">
        <Tabs defaultValue="analysis">
          <TabsList className="grid w-full grid-cols-3">
            <TabsTrigger value="analysis">Analyze</TabsTrigger>
            <TabsTrigger value="qna">Q&A</TabsTrigger>
            <TabsTrigger value="publish">Publish</TabsTrigger>
          </TabsList>

          <TabsContent value="analysis" className="space-y-6 pt-4">
            <div className="flex flex-wrap gap-2">
              <Button
                onClick={onAnalyze}
                disabled={isActionRunning}
                size="sm"
              >
                Analyze
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={onQuestions}
                disabled={isActionRunning}
              >
                Questions
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={onSuggestions}
                disabled={isActionRunning}
              >
                Suggestions
              </Button>
              <Button
                variant="secondary"
                size="sm"
                onClick={onEvaluate}
                disabled={isActionRunning}
              >
                Evaluate
              </Button>
            </div>

            {analysis ? (
              <div className="space-y-2 rounded-lg border p-4">
                <div className="flex items-center justify-between">
                  <p className="font-medium">Analysis</p>
                  <Badge variant="secondary">{analysis.completeness_score}/100</Badge>
                </div>
                <Separator />
                {analysis.best_practices_hints.length ? (
                  <div className="space-y-1">
                    <p className="text-muted-foreground text-xs font-semibold">Hints</p>
                    <ul className="list-disc space-y-1 pl-5 text-sm">
                      {analysis.best_practices_hints.map((h) => (
                        <li key={h}>{h}</li>
                      ))}
                    </ul>
                  </div>
                ) : null}
              </div>
            ) : null}

            {questions?.length ? (
              <div className="space-y-2 rounded-lg border p-4">
                <p className="font-medium">Questions</p>
                <ul className="space-y-2 text-sm">
                  {questions.map((q) => (
                    <li key={q.id} className="space-y-1">
                      <p>• {q.text}</p>
                      {q.rationale ? (
                        <p className="text-muted-foreground text-xs">{q.rationale}</p>
                      ) : null}
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}

            {suggestions.length ? (
              <div className="space-y-2 rounded-lg border p-4">
                <p className="font-medium">Suggestions</p>
                <ul className="space-y-2 text-sm">
                  {suggestions.map((s) => (
                    <li key={s.id} className="flex items-start justify-between gap-3">
                      <p className="leading-6">• {s.text}</p>
                      {s.priority ? <Badge variant="outline">{s.priority}</Badge> : null}
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}

            {evaluation ? (
              <div className="space-y-2 rounded-lg border p-4">
                <p className="font-medium">Evaluation</p>
                <div className="grid gap-2 text-sm">
                  <p>Completeness: {evaluation.completeness}/100</p>
                  <p>Scalability: {evaluation.scalability}/100</p>
                  <p>Tradeoffs: {evaluation.tradeoffs}/100</p>
                </div>
              </div>
            ) : null}
          </TabsContent>

          <TabsContent value="qna" className="space-y-6 pt-4">
            <Button
              onClick={onGenerateDraft}
              disabled={isActionRunning}
              size="sm"
            >
              Generate Draft
            </Button>

            {knowledgeDraft?.notes.length ? (
              <div className="space-y-2 rounded-lg border p-4">
                <p className="text-muted-foreground text-xs font-semibold">Notes</p>
                <ul className="list-disc space-y-1 pl-5 text-sm">
                  {knowledgeDraft.notes.map((n) => (
                    <li key={n}>{n}</li>
                  ))}
                </ul>
              </div>
            ) : null}
          </TabsContent>

          <TabsContent value="publish" className="space-y-4 pt-4">
            <div className="space-y-3">
              <div className="flex items-center justify-between gap-3 rounded-lg border p-3">
                <div className="space-y-1">
                  <p className="text-sm leading-none font-medium">Learning topics</p>
                  <p className="text-muted-foreground text-xs">Save to learning library</p>
                </div>
                <Switch
                  checked={publishLearningTopics}
                  onCheckedChange={onPublishLearningTopicsChange}
                />
              </div>

              <div className="flex items-center justify-between gap-3 rounded-lg border p-3">
                <div className="space-y-1">
                  <p className="text-sm leading-none font-medium">Zettels</p>
                  <p className="text-muted-foreground text-xs">Create zettelkasten cards</p>
                </div>
                <Switch checked={publishZettels} onCheckedChange={onPublishZettelsChange} />
              </div>
            </div>

            <div className="grid gap-3">
              <div className="space-y-2">
                <Label htmlFor="topicTitle" className="text-xs">
                  Topic title
                </Label>
                <Input
                  id="topicTitle"
                  placeholder="Optional"
                  value={topicTitle}
                  onChange={(e) => onTopicTitleChange(e.target.value)}
                  className="h-8 text-xs"
                />
              </div>
            </div>

            <Button
              onClick={onPublish}
              disabled={isActionRunning}
              size="sm"
            >
              Publish
            </Button>

            {publishResult ? (
              <div className="space-y-2 rounded-lg border p-4 text-sm">
                <p className="font-medium">Published</p>
                <p>Topics: {publishResult.artifacts.learning_topic_ids.length}</p>
                <p>Zettels: {publishResult.artifacts.zettel_card_ids.length}</p>
              </div>
            ) : null}
          </TabsContent>
        </Tabs>
      </CardContent>
    </Card>
  );
}
