"use client";

import { Check, Circle, Loader2 } from "lucide-react";

import { cn } from "@/lib/utils";
import { useResearchPlan } from "@/lib/stores/research-store";

export function PlanPanel() {
  const todos = useResearchPlan();

  if (todos.length === 0) {
    return (
      <div className="text-muted-foreground px-4 py-6 text-xs leading-relaxed">
        The orchestrator has not published a plan yet. Once the run starts, the todo list
        will appear here and update in real time.
      </div>
    );
  }

  return (
    <ol className="space-y-2 px-4 py-4">
      {todos.map((todo, idx) => (
        <li key={`${idx}-${todo.content.slice(0, 24)}`} className="flex items-start gap-2">
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
              "text-sm leading-snug",
              todo.status === "completed" ? "text-muted-foreground line-through" : "",
            )}
          >
            {todo.content}
          </span>
        </li>
      ))}
    </ol>
  );
}
