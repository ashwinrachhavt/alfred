"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";
import { BloomProgressBar } from "./bloom-badge";
import { type Zettel } from "./mock-data";

type Props = {
  zettels: Zettel[];
};

export function ReviewFeynman({ zettels }: Props) {
  const withGaps = zettels.filter((z) => z.feynmanGaps.length > 0);
  const [index, setIndex] = useState(0);
  const [explanation, setExplanation] = useState("");
  const [submitted, setSubmitted] = useState(false);

  if (withGaps.length === 0) {
    return (
      <div className="py-16 text-center">
        <p className="font-serif text-xl text-muted-foreground">No concepts to test</p>
        <p className="mt-2 font-mono text-xs text-[var(--alfred-text-tertiary)]">All concepts mastered</p>
      </div>
    );
  }

  const zettel = withGaps[index % withGaps.length];
  // Show fewer gaps for longer explanations (simulating AI evaluation)
  const gapsToShow = explanation.length > 200
    ? zettel.feynmanGaps.slice(0, 1)
    : zettel.feynmanGaps;

  const handleSubmit = () => {
    if (!explanation.trim()) return;
    setSubmitted(true);
  };

  const handleNext = () => {
    setIndex(index + 1);
    setExplanation("");
    setSubmitted(false);
  };

  if (index >= withGaps.length) {
    return (
      <div className="mx-auto max-w-lg py-12 text-center">
        <p className="font-serif text-2xl">Feynman Session Complete</p>
        <p className="mt-4 font-mono text-xs text-[var(--alfred-text-tertiary)]">
          {withGaps.length} concepts tested
        </p>
        <Button className="mt-6 font-mono text-xs" onClick={() => { setIndex(0); setSubmitted(false); setExplanation(""); }}>
          Start Over
        </Button>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-2xl py-6">
      {/* Concept header */}
      <div className="mb-4 flex items-start justify-between">
        <div>
          <p className="font-mono text-[10px] uppercase tracking-widest text-[var(--alfred-text-tertiary)]">
            Feynman Test · {index + 1} of {withGaps.length}
          </p>
        </div>
        <div className="w-32">
          <BloomProgressBar level={zettel.bloomLevel} />
        </div>
      </div>

      {/* Prompt */}
      <p className="font-serif text-xl leading-relaxed mb-4">
        Explain &ldquo;{zettel.title}&rdquo; as if you&rsquo;re teaching a smart 12-year-old.
      </p>

      {/* Writing area */}
      <textarea
        value={explanation}
        onChange={(e) => setExplanation(e.target.value)}
        placeholder="Start explaining in your own words..."
        disabled={submitted}
        className="w-full min-h-[120px] rounded-md border bg-transparent p-4 text-[14px] leading-relaxed outline-none placeholder:text-[var(--alfred-text-tertiary)] focus:border-primary disabled:opacity-60 resize-y"
      />

      {/* Gap detection (shown after submit) */}
      {submitted && (
        <div className="mt-4 space-y-3">
          {gapsToShow.map((gap, i) => (
            <div key={i} className="rounded-r-md border-l-[3px] border-primary bg-[var(--alfred-accent-subtle)] p-4">
              <div className="font-mono text-[9px] uppercase tracking-widest text-primary mb-1.5">
                Gap detected
              </div>
              <p className="text-[13px] leading-relaxed text-foreground">{gap.gap}</p>
              <p className="mt-2 font-mono text-[11px] text-[var(--alfred-text-tertiary)]">
                Source: {gap.sourceHint}
              </p>
            </div>
          ))}

          {gapsToShow.length === 0 && (
            <div className="rounded-r-md border-l-[3px] border-[var(--success)] bg-[rgba(45,106,79,0.08)] p-4">
              <div className="font-mono text-[9px] uppercase tracking-widest text-[var(--success)] mb-1.5">
                Strong explanation
              </div>
              <p className="text-[13px] text-[var(--success)]">No gaps detected. Your understanding looks solid.</p>
            </div>
          )}
        </div>
      )}

      {/* Actions */}
      <div className="mt-4 flex gap-3">
        {!submitted ? (
          <>
            <Button variant="outline" className="font-mono text-xs" onClick={handleNext}>
              Skip
            </Button>
            <Button className="font-mono text-xs" onClick={handleSubmit} disabled={!explanation.trim()}>
              Submit explanation
            </Button>
          </>
        ) : (
          <>
            <Button variant="outline" className="font-mono text-xs" onClick={handleNext}>
              {index < withGaps.length - 1 ? "Next concept" : "Finish"}
            </Button>
            <Button variant="outline" className="font-mono text-xs" onClick={() => setSubmitted(false)}>
              Revise explanation
            </Button>
          </>
        )}
      </div>
    </div>
  );
}
