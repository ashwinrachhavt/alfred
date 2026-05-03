import { TodayDashboard } from "./_components/today-dashboard";
import { TodayViewShell } from "./_components/today-view-shell";

export const metadata = { title: "Today — Polymath" };

type ViewMode = "table" | "kanban" | "calendar";
const VALID_VIEWS: ViewMode[] = ["table", "kanban", "calendar"];

export default async function TodayPage({
  searchParams,
}: {
  searchParams: Promise<{ view?: string; date?: string; week?: string; month?: string }>;
}) {
  const params = await searchParams;
  const view = VALID_VIEWS.includes(params.view as ViewMode) ? (params.view as ViewMode) : null;

  if (!view) {
    return (
      <div className="mx-auto max-w-4xl px-8 py-8">
        <TodayDashboard />
      </div>
    );
  }

  return <TodayViewShell view={view} date={params.date} week={params.week} month={params.month} />;
}
