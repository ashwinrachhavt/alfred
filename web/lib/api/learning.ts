import { apiFetch } from "./client";
import { apiRoutes } from "./routes";

export type DeckItemSource = {
  title: string | null;
  source_url: string | null;
  document_id: string | null;
  captured_at: string | null;
};

export type DeckItem = {
  review_id: number;
  topic_id: number;
  topic_name: string;
  stage: number;
  question: string;
  answer: string | null;
  source: DeckItemSource | null;
  needs_quiz_generation: boolean;
};

export type DailyDeckResponse = {
  items: DeckItem[];
  total_due: number;
  showing: number;
  estimated_minutes: number;
};

export type ReviewCompleteResponse = {
  id: number;
  topic_id: number;
  stage: number;
  iteration: number;
  due_at: string;
  completed_at: string | null;
  score: number | null;
};

export type QuizGenerateResponse = {
  id: number;
  topic_id: number;
  items: { question: string; answer: string | null }[];
};

export async function getDailyDeck(limit = 20): Promise<DailyDeckResponse> {
  return apiFetch(`${apiRoutes.learning.dailyDeck}?limit=${limit}`);
}

export async function completeReview(
  reviewId: number,
  score: number,
): Promise<ReviewCompleteResponse> {
  return apiFetch(`${apiRoutes.learning.reviewsDue.replace("/due", "")}/${reviewId}/complete`, {
    method: "POST",
    body: JSON.stringify({ score }),
    headers: { "Content-Type": "application/json" },
  });
}

export async function generateQuizForTopic(
  topicId: number,
  questionCount = 8,
): Promise<QuizGenerateResponse> {
  return apiFetch(`${apiRoutes.learning.topics}/${topicId}/quiz`, {
    method: "POST",
    body: JSON.stringify({ question_count: questionCount }),
    headers: { "Content-Type": "application/json" },
  });
}
