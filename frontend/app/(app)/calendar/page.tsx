import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export default function CalendarPage() {
  return (
    <div className="mx-auto w-full max-w-6xl px-4 py-10">
      <Card>
        <CardHeader>
          <CardTitle>Calendar & Email</CardTitle>
        </CardHeader>
        <CardContent className="text-muted-foreground text-sm">
          Coming next: OAuth connection cards, calendar views, and email threads.
        </CardContent>
      </Card>
    </div>
  );
}
