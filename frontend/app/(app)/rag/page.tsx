import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export default function RagPage() {
  return (
    <div className="mx-auto w-full max-w-6xl px-4 py-10">
      <Card>
        <CardHeader>
          <CardTitle>Knowledge Assistant (RAG)</CardTitle>
        </CardHeader>
        <CardContent className="text-muted-foreground text-sm">
          Coming next: chat with citations, context viewer, and modes.
        </CardContent>
      </Card>
    </div>
  );
}
