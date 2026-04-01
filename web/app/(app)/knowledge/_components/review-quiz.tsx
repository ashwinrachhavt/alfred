"use client";

import { useState, useMemo } from "react";

import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { BloomBadge } from "./bloom-badge";
import { type Zettel } from "./mock-data";

type Props = {
 zettels: Zettel[];
};

function shuffleArray<T>(arr: T[]): T[] {
 const a = [...arr];
 for (let i = a.length - 1; i > 0; i--) {
 const j = Math.floor(Math.random() * (i + 1));
 [a[i], a[j]] = [a[j], a[i]];
 }
 return a;
}

export function ReviewQuiz({ zettels }: Props) {
 const withQuiz = useMemo(() => zettels.filter((z) => z.quizQuestions.length > 0), [zettels]);
 const [index, setIndex] = useState(0);
 const [selected, setSelected] = useState<number | null>(null);
 const [score, setScore] = useState({ correct: 0, total: 0 });

 // Derive current question safely (may be undefined if index is out of bounds or no quizzes)
 const zettel = withQuiz[index] as (typeof withQuiz)[number] | undefined;
 const q = zettel?.quizQuestions[0];

 // useMemo MUST be called unconditionally (React hooks rules)
 const options = useMemo(
 () => (q ? shuffleArray([q.correct, ...q.distractors]) : []),
 // eslint-disable-next-line react-hooks/exhaustive-deps
 [index, withQuiz.length],
 );

 if (withQuiz.length === 0) {
 return (
 <div className="py-16 text-center">
 <p className="text-xl text-muted-foreground">No quiz questions available</p>
 </div>
 );
 }

 if (index >= withQuiz.length || !zettel || !q) {
 return (
 <div className="mx-auto max-w-md py-12 text-center">
 <p className="text-2xl">Quiz Complete</p>
 <p className="mt-4 font-data text-4xl tabular-nums text-primary">
 {score.correct}/{score.total}
 </p>
 <p className="mt-2 text-xs text-[var(--alfred-text-tertiary)]">
 {Math.round((score.correct / Math.max(1, score.total)) * 100)}% accuracy
 </p>
 <Button className="mt-6 text-xs" onClick={() => { setIndex(0); setSelected(null); setScore({ correct: 0, total: 0 }); }}>
 Retake Quiz
 </Button>
 </div>
 );
 }
 const correctIdx = options.indexOf(q.correct);
 const answered = selected !== null;
 const isCorrect = selected === correctIdx;

 const handleNext = () => {
 setScore({ correct: score.correct + (isCorrect ? 1 : 0), total: score.total + 1 });
 setSelected(null);
 setIndex(index + 1);
 };

 return (
 <div className="mx-auto max-w-lg py-8">
 <div className="mb-6 flex items-center justify-between">
 <span className="font-medium text-[10px] uppercase tracking-widest text-[var(--alfred-text-tertiary)]">
 Question {index + 1} of {withQuiz.length}
 </span>
 <div className="flex items-center gap-2">
 <BloomBadge level={zettel.bloomLevel} />
 <span className="text-[10px] text-[var(--alfred-text-tertiary)]">{zettel.tags[0]}</span>
 </div>
 </div>

 <p className="text-xl leading-relaxed mb-6">{q.question}</p>

 <div className="space-y-2">
 {options.map((opt, i) => {
 const isThis = selected === i;
 const isAnswer = i === correctIdx;
 let borderColor = "var(--border)";
 if (answered && isAnswer) borderColor = "var(--success)";
 else if (answered && isThis && !isCorrect) borderColor = "var(--destructive)";
 else if (isThis) borderColor = "var(--primary)";

 return (
 <button
 key={i}
 onClick={() => !answered && setSelected(i)}
 disabled={answered}
 className={cn(
 "flex w-full items-start gap-3 rounded-md border p-4 text-left transition-all",
 !answered && "hover:border-primary hover:bg-[var(--alfred-accent-subtle)]",
 answered && "cursor-default",
 )}
 style={{ borderColor }}
 >
 <span
 className="mt-0.5 flex size-5 shrink-0 items-center justify-center rounded-full border text-[10px]"
 style={{ borderColor, color: answered && isAnswer ? "var(--success)" : undefined }}
 >
 {String.fromCharCode(65 + i)}
 </span>
 <span className="text-[14px] leading-relaxed">{opt}</span>
 </button>
 );
 })}
 </div>

 {answered && (
 <div className="mt-4 flex items-center justify-between">
 <span className={cn(" text-xs", isCorrect ? "text-[var(--success)]" : "text-[var(--destructive)]")}>
 {isCorrect ? "Correct!" : "Incorrect"}
 </span>
 <Button className="text-xs" onClick={handleNext}>
 {index < withQuiz.length - 1 ? "Next question" : "See results"}
 </Button>
 </div>
 )}
 </div>
 );
}
