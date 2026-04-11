export type BloomLevel = 1 | 2 | 3 | 4 | 5 | 6;

export type Zettel = {
  id: string;
  title: string;
  content: string;
  summary: string;
  preview?: string;
  tags: string[];
  connections: string[];
  status: string;
  bloomLevel: BloomLevel;
  bloomHistory: { date: string; level: BloomLevel; source: "flashcard" | "feynman" | "quiz" }[];
  source: {
    title: string;
    url?: string;
    capturedAt: string;
  };
  lastReviewedAt: string | null;
  nextReviewAt: string | null;
  quizHistory: { attempts: number; correct: number };
  quizQuestions: { question: string; correct: string; distractors: string[] }[];
  feynmanGaps: { gap: string; sourceHint: string }[];
  createdAt: string;
  updatedAt: string;
};

export const BLOOM_LABELS: Record<BloomLevel, string> = {
  1: "Remember",
  2: "Understand",
  3: "Apply",
  4: "Analyze",
  5: "Evaluate",
  6: "Create",
};

export const BLOOM_COLORS: Record<BloomLevel, string> = {
  1: "var(--destructive)",
  2: "var(--warning)",
  3: "var(--warning)",
  4: "var(--success)",
  5: "var(--success)",
  6: "var(--primary)",
};

export const MOCK_ZETTELS: Zettel[] = [
  {
    id: "z1",
    title: "Emergence in complex systems",
    content: "The behavior of a complex system is not derivable from the behavior of its components in isolation. Emergence arises from interactions, feedback loops, and nonlinear dynamics — not from the properties of individual parts.",
    summary: "Complex systems exhibit behaviors that cannot be predicted from individual components alone.",
    tags: ["complexity", "epistemology", "systems"],
    status: "active",
    connections: ["z2", "z6", "z8", "z10"],
    bloomLevel: 5,
    bloomHistory: [
      { date: "2026-03-15", level: 2, source: "flashcard" },
      { date: "2026-03-18", level: 4, source: "feynman" },
      { date: "2026-03-20", level: 5, source: "feynman" },
    ],
    source: { title: "Thinking in Systems — Donella Meadows, Ch. 3", capturedAt: "2026-03-14T10:00:00Z" },
    lastReviewedAt: "2026-03-20T14:30:00Z",
    nextReviewAt: "2026-03-27T14:30:00Z",
    quizHistory: { attempts: 4, correct: 3 },
    quizQuestions: [
      { question: "What mechanism causes emergence in complex systems?", correct: "Feedback loops and nonlinear interactions between components", distractors: ["The sum of individual component properties", "Random chance and probability", "Top-down coordination by a central controller"] },
      { question: "Why can't emergent behavior be predicted from parts alone?", correct: "Because interactions create new properties not present in individual components", distractors: ["Because the parts are too small to measure", "Because we lack computational power", "Because emergence is random and unpredictable"] },
    ],
    feynmanGaps: [
      { gap: "You explained WHAT emergence is but not WHY it happens. What role do feedback loops play as the mechanism?", sourceHint: "Meadows Ch. 3 — feedback loops section" },
      { gap: "Can you give an example of emergence in a non-biological system?", sourceHint: "Meadows Ch. 5 — economic emergence" },
    ],
    createdAt: "2026-03-14T10:00:00Z",
    updatedAt: "2026-03-20T14:30:00Z",
  },
  {
    id: "z2",
    title: "Paradigm shifts (Kuhn)",
    content: "Normal science operates within paradigms that define both the problems worth solving and the methods for solving them. Anomalies accumulate until a crisis triggers a revolution — a fundamentally new framework replaces the old.",
    summary: "Scientific progress isn't linear — it happens through revolutionary paradigm shifts when anomalies overwhelm the existing framework.",
    tags: ["philosophy", "epistemology"],
    status: "active",
    connections: ["z1", "z5"],
    bloomLevel: 3,
    bloomHistory: [
      { date: "2026-03-16", level: 1, source: "flashcard" },
      { date: "2026-03-19", level: 3, source: "quiz" },
    ],
    source: { title: "The Structure of Scientific Revolutions — Thomas Kuhn, Ch. 4", capturedAt: "2026-03-15T09:00:00Z" },
    lastReviewedAt: "2026-03-19T11:00:00Z",
    nextReviewAt: "2026-03-22T11:00:00Z",
    quizHistory: { attempts: 3, correct: 2 },
    quizQuestions: [
      { question: "What triggers a scientific revolution according to Kuhn?", correct: "Accumulated anomalies that the current paradigm cannot explain", distractors: ["A single brilliant discovery", "Funding changes in research institutions", "Political pressure from governments"] },
    ],
    feynmanGaps: [
      { gap: "You described paradigm shifts but didn't explain what 'normal science' looks like day-to-day.", sourceHint: "Kuhn Ch. 2 — the nature of normal science" },
    ],
    createdAt: "2026-03-15T09:00:00Z",
    updatedAt: "2026-03-19T11:00:00Z",
  },
  {
    id: "z3",
    title: "Aggregation theory limits",
    content: "Ben Thompson argues that platform aggregators gain power by owning demand rather than supply. But aggregation has limits: when trust degrades, when regulation intervenes, or when the supply side finds alternative distribution.",
    summary: "Platform scale has diminishing returns when trust, regulation, or supply-side alternatives erode the aggregator's demand monopoly.",
    tags: ["strategy", "tech"],
    status: "active",
    connections: ["z7"],
    bloomLevel: 4,
    bloomHistory: [
      { date: "2026-03-17", level: 2, source: "flashcard" },
      { date: "2026-03-20", level: 4, source: "feynman" },
    ],
    source: { title: "Stratechery — 'Scale is not a strategy'", url: "https://stratechery.com", capturedAt: "2026-03-16T15:00:00Z" },
    lastReviewedAt: "2026-03-20T10:00:00Z",
    nextReviewAt: "2026-03-27T10:00:00Z",
    quizHistory: { attempts: 2, correct: 2 },
    quizQuestions: [
      { question: "What do aggregators own that gives them power?", correct: "Demand — the relationship with end users", distractors: ["Supply — the content or products", "Infrastructure — the servers and networks", "Talent — the best engineers"] },
    ],
    feynmanGaps: [
      { gap: "You explained aggregation but didn't address the limits. What happens when trust degrades?", sourceHint: "Thompson's analysis of Facebook trust erosion" },
    ],
    createdAt: "2026-03-16T15:00:00Z",
    updatedAt: "2026-03-20T10:00:00Z",
  },
  {
    id: "z4",
    title: "SCRAM channel binding",
    content: "SCRAM (Salted Challenge Response Authentication Mechanism) with channel binding ties the authentication to the TLS channel, preventing man-in-the-middle attacks on database credentials. PostgreSQL supports this via the channel_binding=require connection parameter.",
    summary: "PostgreSQL authentication mechanism that binds credentials to the TLS channel, preventing credential interception.",
    tags: ["backend", "security"],
    status: "active",
    connections: [],
    bloomLevel: 1,
    bloomHistory: [],
    source: { title: "PostgreSQL Documentation — Authentication", capturedAt: "2026-03-21T08:00:00Z" },
    lastReviewedAt: null,
    nextReviewAt: "2026-03-22T08:00:00Z",
    quizHistory: { attempts: 0, correct: 0 },
    quizQuestions: [
      { question: "What does SCRAM channel binding protect against?", correct: "Man-in-the-middle attacks on database credentials", distractors: ["SQL injection attacks", "Brute force password cracking", "Denial of service attacks"] },
    ],
    feynmanGaps: [
      { gap: "You haven't reviewed this concept yet. Start by explaining what SCRAM stands for and why channel binding matters.", sourceHint: "PostgreSQL docs — SCRAM-SHA-256 section" },
    ],
    createdAt: "2026-03-21T08:00:00Z",
    updatedAt: "2026-03-21T08:00:00Z",
  },
  {
    id: "z5",
    title: "Consciousness as self-model (Bach)",
    content: "Joscha Bach frames consciousness as a 'self-model that models itself modeling.' The mind creates a compressed representation of itself and its relationship to the world, and consciousness is the experience of running that model.",
    summary: "Bach's theory: consciousness is a recursive self-model — the mind modeling its own modeling process.",
    tags: ["philosophy", "AI", "consciousness"],
    status: "active",
    connections: ["z1", "z2"],
    bloomLevel: 2,
    bloomHistory: [
      { date: "2026-03-18", level: 2, source: "flashcard" },
    ],
    source: { title: "Podcast: Joscha Bach on Lex Fridman #392", capturedAt: "2026-03-17T20:00:00Z" },
    lastReviewedAt: "2026-03-18T09:00:00Z",
    nextReviewAt: "2026-03-19T09:00:00Z",
    quizHistory: { attempts: 1, correct: 0 },
    quizQuestions: [
      { question: "How does Bach define consciousness?", correct: "A self-model that models itself modeling the world", distractors: ["An emergent property of neural complexity", "A quantum phenomenon in microtubules", "A social construct without physical basis"] },
    ],
    feynmanGaps: [
      { gap: "You restated Bach's definition but didn't explain what 'recursive self-modeling' means in practice.", sourceHint: "Bach's framework of computational consciousness" },
    ],
    createdAt: "2026-03-17T20:00:00Z",
    updatedAt: "2026-03-18T09:00:00Z",
  },
  {
    id: "z6",
    title: "Systems thinking (Meadows)",
    content: "A system is more than the sum of its parts. It exhibits adaptive, dynamic, goal-seeking behavior through feedback loops, delays, and leverage points. Understanding systems requires thinking about relationships and flows, not just components.",
    summary: "Meadows' framework: systems are defined by relationships, feedback loops, and leverage points — not by their parts.",
    tags: ["systems", "complexity"],
    status: "active",
    connections: ["z1", "z8"],
    bloomLevel: 5,
    bloomHistory: [
      { date: "2026-03-14", level: 3, source: "feynman" },
      { date: "2026-03-17", level: 4, source: "quiz" },
      { date: "2026-03-20", level: 5, source: "feynman" },
    ],
    source: { title: "Thinking in Systems — Donella Meadows, Ch. 1", capturedAt: "2026-03-13T14:00:00Z" },
    lastReviewedAt: "2026-03-20T16:00:00Z",
    nextReviewAt: "2026-04-19T16:00:00Z",
    quizHistory: { attempts: 5, correct: 5 },
    quizQuestions: [
      { question: "What are the three key elements of a system according to Meadows?", correct: "Elements, interconnections, and purpose", distractors: ["Inputs, processes, and outputs", "Structure, behavior, and function", "Parts, wholes, and boundaries"] },
    ],
    feynmanGaps: [],
    createdAt: "2026-03-13T14:00:00Z",
    updatedAt: "2026-03-20T16:00:00Z",
  },
  {
    id: "z7",
    title: "Zettelkasten method (Luhmann)",
    content: "Niklas Luhmann's card-based note-taking system works because each note is atomic (one idea), addressed (unique ID), and connected (explicit links to other notes). The power isn't in storage — it's in the connections that emerge over time.",
    summary: "Luhmann's method: atomic notes with explicit connections create emergent knowledge structures over time.",
    tags: ["PKM", "methodology"],
    status: "active",
    connections: ["z3", "z8"],
    bloomLevel: 6,
    bloomHistory: [
      { date: "2026-03-10", level: 3, source: "flashcard" },
      { date: "2026-03-14", level: 5, source: "feynman" },
      { date: "2026-03-19", level: 6, source: "feynman" },
    ],
    source: { title: "How to Take Smart Notes — Sönke Ahrens", capturedAt: "2026-03-09T11:00:00Z" },
    lastReviewedAt: "2026-03-19T15:00:00Z",
    nextReviewAt: "2026-04-18T15:00:00Z",
    quizHistory: { attempts: 6, correct: 6 },
    quizQuestions: [
      { question: "What makes a zettel effective according to Luhmann?", correct: "It's atomic (one idea), addressed (unique ID), and connected (links to others)", distractors: ["It's comprehensive and covers the full topic", "It's organized in folders by category", "It's written in formal academic language"] },
    ],
    feynmanGaps: [],
    createdAt: "2026-03-09T11:00:00Z",
    updatedAt: "2026-03-19T15:00:00Z",
  },
  {
    id: "z8",
    title: "Feedback loops and leverage points",
    content: "Meadows identifies 12 places to intervene in a system, ranked by effectiveness. The most powerful leverage points are paradigms and goals — not parameters like tax rates or subsidies. Most people push on the least effective points.",
    summary: "The most powerful leverage points in systems are paradigms and goals, not parameters — but most interventions target the weakest points.",
    tags: ["systems", "strategy"],
    status: "active",
    connections: ["z1", "z6"],
    bloomLevel: 4,
    bloomHistory: [
      { date: "2026-03-15", level: 2, source: "flashcard" },
      { date: "2026-03-19", level: 4, source: "quiz" },
    ],
    source: { title: "Thinking in Systems — Donella Meadows, Ch. 6", capturedAt: "2026-03-14T16:00:00Z" },
    lastReviewedAt: "2026-03-19T13:00:00Z",
    nextReviewAt: "2026-03-26T13:00:00Z",
    quizHistory: { attempts: 3, correct: 3 },
    quizQuestions: [
      { question: "What is the most powerful leverage point in a system?", correct: "The paradigm — the mindset out of which the system arises", distractors: ["The flow rates of resources", "The rules of the system", "The information flows"] },
    ],
    feynmanGaps: [
      { gap: "You listed leverage points but didn't explain WHY paradigms are more powerful than rules or flows.", sourceHint: "Meadows Ch. 6 — hierarchy of leverage points" },
    ],
    createdAt: "2026-03-14T16:00:00Z",
    updatedAt: "2026-03-19T13:00:00Z",
  },
  {
    id: "z9",
    title: "Feynman technique for learning",
    content: "Richard Feynman's learning method: (1) Choose a concept, (2) Teach it to a child, (3) Identify gaps where your explanation breaks down, (4) Simplify and fill gaps. The act of teaching forces you to confront what you don't actually understand.",
    summary: "Learn by teaching: explain a concept simply, find where your explanation breaks, fill the gaps.",
    tags: ["learning", "methodology"],
    status: "active",
    connections: ["z10", "z7"],
    bloomLevel: 5,
    bloomHistory: [
      { date: "2026-03-12", level: 3, source: "flashcard" },
      { date: "2026-03-16", level: 5, source: "feynman" },
    ],
    source: { title: "Feynman's Lost Lecture — David Goodstein", capturedAt: "2026-03-11T09:00:00Z" },
    lastReviewedAt: "2026-03-16T10:00:00Z",
    nextReviewAt: "2026-04-15T10:00:00Z",
    quizHistory: { attempts: 2, correct: 2 },
    quizQuestions: [
      { question: "What is the key insight of the Feynman technique?", correct: "Teaching reveals gaps in understanding that studying alone misses", distractors: ["Repetition is the best way to memorize", "Visual learners should draw diagrams", "Speed reading improves comprehension"] },
    ],
    feynmanGaps: [],
    createdAt: "2026-03-11T09:00:00Z",
    updatedAt: "2026-03-16T10:00:00Z",
  },
  {
    id: "z10",
    title: "Bloom's taxonomy of knowledge",
    content: "Benjamin Bloom's framework ranks cognitive skills: Remember → Understand → Apply → Analyze → Evaluate → Create. Each level requires mastery of the levels below it. Most education tests only Remember and Understand.",
    summary: "Bloom's 6-level hierarchy: knowing a fact (Remember) is fundamentally different from being able to create with it (Create).",
    tags: ["learning", "epistemology"],
    status: "active",
    connections: ["z1", "z9"],
    bloomLevel: 4,
    bloomHistory: [
      { date: "2026-03-13", level: 2, source: "flashcard" },
      { date: "2026-03-17", level: 3, source: "quiz" },
      { date: "2026-03-20", level: 4, source: "feynman" },
    ],
    source: { title: "Taxonomy of Educational Objectives — Benjamin Bloom", capturedAt: "2026-03-12T14:00:00Z" },
    lastReviewedAt: "2026-03-20T11:00:00Z",
    nextReviewAt: "2026-03-27T11:00:00Z",
    quizHistory: { attempts: 4, correct: 3 },
    quizQuestions: [
      { question: "What is the highest level in Bloom's taxonomy?", correct: "Create — synthesizing new ideas from existing knowledge", distractors: ["Evaluate — judging the value of information", "Analyze — breaking down complex ideas", "Apply — using knowledge in new situations"] },
    ],
    feynmanGaps: [
      { gap: "You listed the levels but didn't explain why most education only tests the bottom two.", sourceHint: "Bloom's original research on educational testing" },
    ],
    createdAt: "2026-03-12T14:00:00Z",
    updatedAt: "2026-03-20T11:00:00Z",
  },
  {
    id: "z11",
    title: "DDIA: Replication strategies",
    content: "Kleppmann outlines three replication approaches: single-leader (simple, consistent, bottleneck), multi-leader (better write availability, conflict resolution needed), and leaderless (Dynamo-style, quorum reads/writes, high availability).",
    summary: "Three replication models trade off consistency, availability, and complexity differently.",
    tags: ["system-design", "backend"],
    status: "active",
    connections: ["z12"],
    bloomLevel: 3,
    bloomHistory: [
      { date: "2026-03-18", level: 1, source: "flashcard" },
      { date: "2026-03-21", level: 3, source: "quiz" },
    ],
    source: { title: "Designing Data-Intensive Applications — Martin Kleppmann, Ch. 5", capturedAt: "2026-03-17T11:00:00Z" },
    lastReviewedAt: "2026-03-21T09:00:00Z",
    nextReviewAt: "2026-03-28T09:00:00Z",
    quizHistory: { attempts: 3, correct: 2 },
    quizQuestions: [
      { question: "What is the main trade-off of multi-leader replication?", correct: "Better write availability but requires conflict resolution", distractors: ["Lower latency but higher cost", "Simpler architecture but lower throughput", "Better consistency but single point of failure"] },
    ],
    feynmanGaps: [
      { gap: "You described the three models but didn't explain when to choose each one.", sourceHint: "DDIA Ch. 5 — use cases for each replication strategy" },
    ],
    createdAt: "2026-03-17T11:00:00Z",
    updatedAt: "2026-03-21T09:00:00Z",
  },
  {
    id: "z12",
    title: "CAP theorem and its practical limits",
    content: "The CAP theorem states that a distributed system can provide at most two of: Consistency, Availability, Partition tolerance. In practice, since network partitions are inevitable, the real choice is between CP (consistent but may be unavailable) and AP (available but may be inconsistent).",
    summary: "CAP theorem: since partitions are inevitable, you're really choosing between consistency and availability.",
    tags: ["system-design", "distributed-systems"],
    status: "active",
    connections: ["z11"],
    bloomLevel: 3,
    bloomHistory: [
      { date: "2026-03-19", level: 2, source: "flashcard" },
      { date: "2026-03-21", level: 3, source: "flashcard" },
    ],
    source: { title: "DDIA — Martin Kleppmann, Ch. 9", capturedAt: "2026-03-18T16:00:00Z" },
    lastReviewedAt: "2026-03-21T10:00:00Z",
    nextReviewAt: "2026-03-28T10:00:00Z",
    quizHistory: { attempts: 2, correct: 1 },
    quizQuestions: [
      { question: "Why is the CAP theorem's 'pick two' framing misleading?", correct: "Because network partitions are inevitable, so the real choice is CP vs AP", distractors: ["Because you can actually achieve all three with enough hardware", "Because consistency is always more important than availability", "Because the theorem only applies to relational databases"] },
    ],
    feynmanGaps: [
      { gap: "You stated the theorem but didn't explain what 'partition tolerance' actually means in practice.", sourceHint: "DDIA Ch. 9 — network partitions section" },
    ],
    createdAt: "2026-03-18T16:00:00Z",
    updatedAt: "2026-03-21T10:00:00Z",
  },
];

/** Get all unique tags across all zettels */
export function getAllTags(zettels: Zettel[]): string[] {
  const tags = new Set<string>();
  for (const z of zettels) {
    for (const t of z.tags) tags.add(t);
  }
  return Array.from(tags).sort();
}

/** Count zettels due for review */
export function getDueCount(zettels: Zettel[]): number {
  const now = new Date();
  return zettels.filter((z) => z.nextReviewAt && new Date(z.nextReviewAt) <= now).length;
}
