"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";
import { BloomBadge } from "./bloom-badge";
import { BLOOM_LABELS, type Zettel } from "./mock-data";

type Props = {
 zettels: Zettel[];
};

export function ReviewFlashcard({ zettels }: Props) {
 const due = zettels.filter((z) => z.quizQuestions.length > 0);
 const [index, setIndex] = useState(0);
 const [revealed, setRevealed] = useState(false);
 const [results, setResults] = useState<("know" | "dont_know")[]>([]);

 if (due.length === 0) {
 return (
 <div className="py-16 text-center">
 <p className="text-xl text-muted-foreground">No cards to review</p>
 <p className="mt-2 text-xs text-[var(--alfred-text-tertiary)]">All caught up</p>
 </div>
 );
 }

 const zettel = due[index % due.length];
 const question = zettel.quizQuestions[0];
 const cardNum = index + 1;
 const total = due.length;

 const advance = (result: "know" | "dont_know") => {
 setResults([...results, result]);
 setRevealed(false);
 setIndex(index + 1);
 };

 if (index >= due.length) {
 const correct = results.filter((r) => r === "know").length;
 return (
 <div className="mx-auto max-w-md py-12 text-center">
 <p className="text-2xl">Session Complete</p>
 <p className="mt-4 font-data text-4xl tabular-nums text-primary">
 {correct}/{results.length}
 </p>
 <p className="mt-2 text-xs text-[var(--alfred-text-tertiary)]">
 {Math.round((correct / results.length) * 100)}% retention
 </p>
 <Button className="mt-6 text-xs" onClick={() => { setIndex(0); setResults([]); }}>
 Review Again
 </Button>
 </div>
 );
 }

 return (
 <div className="mx-auto max-w-lg py-8">
 {/* Progress */}
 <div className="mb-6 text-center font-medium text-[10px] uppercase tracking-widest text-[var(--alfred-text-tertiary)]">
 Card {cardNum} of {total}
 </div>

 {/* Card */}
 <div className="rounded-lg border p-8 text-center">
 <div className="mb-2 flex items-center justify-center gap-2">
 <BloomBadge level={zettel.bloomLevel} />
 <span className="text-[10px] text-[var(--alfred-text-tertiary)]">{zettel.tags[0]}</span>
 </div>

 <p className="text-xl leading-relaxed">{question.question}</p>

 {!revealed ? (
 <div className="mt-8 flex justify-center gap-3">
 <Button variant="outline" className="text-xs" onClick={() => advance("dont_know")}>
 I don't know
 </Button>
 <Button className="text-xs" onClick={() => setRevealed(true)}>
 Reveal answer
 </Button>
 <Button variant="outline" className="text-xs" onClick={() => advance("know")}>
 I know this
 </Button>
 </div>
 ) : (
 <div className="mt-6">
 <div className="rounded-md border-l-3 border-primary bg-[var(--alfred-accent-subtle)] p-4 text-left">
 <div className="font-medium text-[9px] uppercase tracking-widest text-primary mb-2">Answer</div>
 <p className="text-[14px] leading-relaxed">{question.correct}</p>
 </div>
 <div className="mt-6 flex justify-center gap-3">
 <Button variant="outline" className="text-xs" onClick={() => advance("dont_know")}>
 Got it wrong
 </Button>
 <Button className="text-xs" onClick={() => advance("know")}>
 Got it right
 </Button>
 </div>
 </div>
 )}

 <p className="mt-6 text-[10px] text-[var(--alfred-text-tertiary)]">
 Bloom target: {BLOOM_LABELS[zettel.bloomLevel]} → {BLOOM_LABELS[Math.min(6, zettel.bloomLevel + 1) as 1 | 2 | 3 | 4 | 5 | 6]}
 </p>
 </div>
 </div>
 );
}
