"use client";

import { useState } from "react";
import { BookOpen, MessageSquare, ListChecks } from "lucide-react";

import { cn } from "@/lib/utils";
import { type Zettel } from "./mock-data";
import { ReviewFlashcard } from "./review-flashcard";
import { ReviewFeynman } from "./review-feynman";
import { ReviewQuiz } from "./review-quiz";

type ReviewMode = "flashcard" | "feynman" | "quiz";

const modes: { key: ReviewMode; label: string; icon: typeof BookOpen }[] = [
 { key: "flashcard", label: "Flashcard", icon: BookOpen },
 { key: "feynman", label: "Feynman", icon: MessageSquare },
 { key: "quiz", label: "Quiz", icon: ListChecks },
];

type Props = {
 zettels: Zettel[];
};

export function ReviewStation({ zettels }: Props) {
 const [mode, setMode] = useState<ReviewMode>("flashcard");

 return (
 <div className="border-t border-[var(--alfred-ruled-line)]">
 {/* Header + tabs */}
 <div className="flex items-center justify-between px-6 pt-5 pb-3">
 <div>
 <h2 className="text-xl">Review Station</h2>
 <p className="mt-0.5 font-medium text-[10px] uppercase tracking-widest text-[var(--alfred-text-tertiary)]">
 Test your understanding
 </p>
 </div>
 <div className="flex gap-1">
 {modes.map((m) => (
 <button
 key={m.key}
 onClick={() => setMode(m.key)}
 className={cn(
 "flex items-center gap-1.5 rounded-md px-3 py-1.5 text-[11px] uppercase tracking-wider transition-colors",
 mode === m.key
 ? "bg-[var(--alfred-accent-muted)] text-primary"
 : "text-muted-foreground hover:bg-[var(--alfred-accent-subtle)] hover:text-foreground",
 )}
 >
 <m.icon className="size-3.5" />
 {m.label}
 </button>
 ))}
 </div>
 </div>

 {/* Content */}
 <div className="px-6 pb-6">
 {mode === "flashcard" && <ReviewFlashcard zettels={zettels} />}
 {mode === "feynman" && <ReviewFeynman zettels={zettels} />}
 {mode === "quiz" && <ReviewQuiz zettels={zettels} />}
 </div>
 </div>
 );
}
