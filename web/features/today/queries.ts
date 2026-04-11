import { addMonths, endOfMonth, format, startOfMonth, subMonths } from "date-fns";
import { useQuery } from "@tanstack/react-query";

import { getTodayBriefing, getTodayCalendar } from "@/lib/api/today";

export function toIsoDay(value: Date): string {
  return format(value, "yyyy-MM-dd");
}

export function useTodayBriefing(selectedDate: Date, timeZone: string) {
  const day = toIsoDay(selectedDate);

  return useQuery({
    enabled: Boolean(timeZone),
    queryKey: ["today", "briefing", day, timeZone],
    queryFn: () => getTodayBriefing({ date: day, tz: timeZone }),
    staleTime: 60_000,
  });
}

export function useTodayCalendar(month: Date, timeZone: string) {
  const startDate = toIsoDay(startOfMonth(subMonths(month, 1)));
  const endDate = toIsoDay(endOfMonth(addMonths(month, 1)));

  return useQuery({
    enabled: Boolean(timeZone),
    queryKey: ["today", "calendar", startDate, endDate, timeZone],
    queryFn: () =>
      getTodayCalendar({
        start_date: startDate,
        end_date: endDate,
        tz: timeZone,
      }),
    staleTime: 60_000,
  });
}
