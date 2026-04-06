import { TodayDashboard } from "./_components/today-dashboard";

export const metadata = { title: "Today — Alfred" };

export default function TodayPage() {
  return (
    <div className="mx-auto max-w-4xl px-8 py-8">
      <TodayDashboard />
    </div>
  );
}
