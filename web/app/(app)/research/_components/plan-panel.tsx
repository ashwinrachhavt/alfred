"use client";

import { Check, Circle, Loader2 } from "lucide-react";

import { cn } from "@/lib/utils";
import { useResearchPlan } from "@/lib/stores/research-store";

export function PlanPanel() {
  const todos = useResearchPlan();

  if (todos.length === 0) {
    return (
      <div className="px-5 py-6">
        <div className="rounded-md border border-dashed border-border/70 bg-muted/10 px-4 py-5">
          <p className="text-sm text-foreground">No plan yet</p>
          <p className="mt-2 text-xs leading-5 text-muted-foreground">
            The run will publish its working list here.
          </p>
        </div>
      </div>
    );
  }

  return (
    <ol className="space-y-2 px-5 py-4">
      {todos.map((todo, idx) => (
        <li
          key={`${idx}-${todo.content.slice(0, 24)}`}
          className="rounded-md border border-border/60 bg-background/35 px-3 py-2.5"
        >
          <div className="flex items-start gap-2.5">
            <span className="mt-0.5 shrink-0">
              {todo.status === "completed" ? (
                <Check className="text-primary h-3.5 w-3.5" />
              ) : todo.status === "in_progress" ? (
                <Loader2 className="text-primary h-3.5 w-3.5 animate-spin" />
              ) : (
                <Circle className="text-muted-foreground h-3.5 w-3.5" />
              )}
            </span>
            <span
              className={cn(
                "text-sm leading-5",
                todo.status === "completed" ? "text-muted-foreground line-through" : "",
              )}
            >
              {todo.content}
            </span>
          </div>
        </li>
      ))}
    </ol>
  );
}
