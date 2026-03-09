"use client";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";

export interface SessionAiDialogProps {
  isOpen: boolean;
  onOpenChange: (open: boolean) => void;
  aiPrompt: string;
  onAiPromptChange: (value: string) => void;
  isGenerating: boolean;
  generationError: string | null;
  onGenerate: () => void;
}

export function SessionAiDialog({
  isOpen,
  onOpenChange,
  aiPrompt,
  onAiPromptChange,
  isGenerating,
  generationError,
  onGenerate,
}: SessionAiDialogProps) {
  return (
    <Dialog open={isOpen} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Generate system diagram</DialogTitle>
          <DialogDescription>
            Describe the architecture you want. Alfred will generate a new Excalidraw diagram.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-2">
          <Label htmlFor="ai-diagram-prompt">Prompt</Label>
          <Textarea
            id="ai-diagram-prompt"
            value={aiPrompt}
            onChange={(e) => onAiPromptChange(e.target.value)}
            rows={6}
            className="resize-none"
            placeholder="Example: Design a URL shortener with analytics, rate limiting, and a queue-based write path."
          />
          {generationError ? (
            <Alert variant="destructive" className="px-3 py-2">
              <AlertDescription className="text-destructive">
                {generationError}
              </AlertDescription>
            </Alert>
          ) : null}
        </div>

        <DialogFooter>
          <Button
            variant="outline"
            onClick={() => onOpenChange(false)}
            disabled={isGenerating}
          >
            Cancel
          </Button>
          <Button
            onClick={onGenerate}
            disabled={isGenerating || !aiPrompt.trim()}
          >
            {isGenerating ? "Generating..." : "Generate"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
