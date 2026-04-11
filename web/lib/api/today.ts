import { apiFetch } from "@/lib/api/client";
import { apiRoutes } from "@/lib/api/routes";

export type TodayCaptureItem = {
  id: string;
  title: string;
  source_url: string | null;
  pipeline_status: string;
  content_type: string | null;
  created_at: string | null;
};

export type TodayStoredCardItem = {
  card_id: number;
  title: string;
  topic: string | null;
  status: string;
  tags: string[];
  created_at: string | null;
};

export type TodayConnectionItem = {
  link_id: number;
  from_card_id: number;
  from_title: string;
  to_card_id: number;
  to_title: string;
  type: string;
  created_at: string | null;
};

export type TodayReviewItem = {
  review_id: number;
  card_id: number;
  card_title: string;
  stage: number;
  due_at: string | null;
  completed_at: string | null;
  status: string;
};

export type TodayGapItem = {
  card_id: number;
  title: string;
  created_at: string | null;
};

export type TodayBriefingStats = {
  total_captures: number;
  total_cards_created: number;
  total_connections: number;
  total_reviews_due: number;
  total_reviews_completed: number;
  total_gaps: number;
  total_events: number;
  total_cards: number;
  total_links: number;
};

export type TodayBriefingResponse = {
  date: string;
  timezone: string;
  generated_at: string;
  captures: TodayCaptureItem[];
  stored_cards: TodayStoredCardItem[];
  connections: TodayConnectionItem[];
  reviews: TodayReviewItem[];
  gaps: TodayGapItem[];
  stats: TodayBriefingStats;
};

export type TodayCalendarDay = {
  date: string;
  captures: number;
  stored_cards: number;
  connections: number;
  reviews_due: number;
  reviews_completed: number;
  gaps: number;
  total_events: number;
};

export type TodayCalendarResponse = {
  start_date: string;
  end_date: string;
  timezone: string;
  days: TodayCalendarDay[];
};

type TodayBriefingParams = {
  date?: string;
  tz?: string;
};

type TodayCalendarParams = {
  start_date?: string;
  end_date?: string;
  days?: number;
  tz?: string;
};

function buildQuery(params: Record<string, string | number | undefined>): string {
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined) continue;
    query.set(key, String(value));
  }
  return query.toString();
}

export async function getTodayBriefing(
  params: TodayBriefingParams = {},
): Promise<TodayBriefingResponse> {
  const query = buildQuery(params);
  const url = query ? `${apiRoutes.today.briefing}?${query}` : apiRoutes.today.briefing;
  return apiFetch<TodayBriefingResponse>(url, { cache: "no-store" });
}

export async function getTodayCalendar(
  params: TodayCalendarParams = {},
): Promise<TodayCalendarResponse> {
  const query = buildQuery(params);
  const url = query ? `${apiRoutes.today.calendar}?${query}` : apiRoutes.today.calendar;
  return apiFetch<TodayCalendarResponse>(url, { cache: "no-store" });
}
