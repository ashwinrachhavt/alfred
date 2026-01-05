import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export default function DocumentsPage() {
  return (
    <div className="mx-auto w-full max-w-6xl px-4 py-10">
      <Card>
        <CardHeader>
          <CardTitle>Documents & Notes</CardTitle>
        </CardHeader>
        <CardContent className="text-muted-foreground text-sm">
          Coming next: uploads, rich notes, tagging, and search.
        </CardContent>
      </Card>
    </div>
  );
}
