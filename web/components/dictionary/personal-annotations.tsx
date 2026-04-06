"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";

export function PersonalAnnotations({
  notes,
  onSave,
  isSaving,
}: {
  notes: string | null;
  onSave: (text: string) => void;
  isSaving?: boolean;
}) {
  const [text, setText] = useState(notes ?? "");
  const [editing, setEditing] = useState(false);
  const hasChanged = text !== (notes ?? "");

  return (
    <div>
      <span className="font-mono text-xs uppercase tracking-wider text-muted-foreground">
        Your Notes
      </span>
      {editing ? (
        <div className="mt-2 space-y-2">
          <Textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder="Add your own notes, mnemonics, or connections..."
            className="min-h-[80px] resize-y"
          />
          <div className="flex gap-2">
            <Button
              size="sm"
              onClick={() => {
                onSave(text);
                setEditing(false);
              }}
              disabled={!hasChanged || isSaving}
            >
              Save
            </Button>
            <Button
              size="sm"
              variant="ghost"
              onClick={() => {
                setText(notes ?? "");
                setEditing(false);
              }}
            >
              Cancel
            </Button>
          </div>
        </div>
      ) : (
        <div
          className="mt-2 cursor-pointer rounded-md border border-dashed p-3 text-sm text-muted-foreground hover:border-foreground/30 transition-colors"
          onClick={() => setEditing(true)}
        >
          {notes || "Click to add your notes..."}
        </div>
      )}
    </div>
  );
}
