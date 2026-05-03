import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";

import { Section } from "./primitives";

export function PatternsTab() {
 return (
 <>
 <Section
 title="Empty states"
 description="Explain what’s missing, why it’s missing, and what to do next."
 >
 <Card>
 <CardContent className="pt-6">
 <EmptyState
 title="No documents yet"
 description="Create your first document to start building a searchable knowledge base."
 action={
 <Button type="button" size="sm">
 Create document
 </Button>
 }
 />
 </CardContent>
 </Card>
 </Section>

 <Section title="Content hierarchy" description="One primary action per surface.">
 <div className="grid gap-4 md:grid-cols-2">
 <Card>
 <CardHeader>
 <CardTitle className="text-base">Primary surface</CardTitle>
 </CardHeader>
 <CardContent className="space-y-3">
 <p className="text-muted-foreground text-sm">
 Use a single primary action and keep secondary actions visually quieter.
 </p>
 <div className="flex flex-wrap gap-2">
 <Button size="sm">Primary</Button>
 <Button size="sm" variant="outline">
 Secondary
 </Button>
 <Button size="sm" variant="ghost">
 Tertiary
 </Button>
 </div>
 </CardContent>
 </Card>

 <Card>
 <CardHeader>
 <CardTitle className="text-base">Muted guidance</CardTitle>
 </CardHeader>
 <CardContent className="space-y-3">
 <p className="text-muted-foreground text-sm">
 Use{" "}
 <code className="bg-muted/40 rounded px-1.5 py-0.5">
 text-muted-foreground
 </code>{" "}
 for descriptions and helper text.
 </p>
 <div className="rounded-lg border p-4">
 <div className="text-sm font-medium">Tip</div>
 <div className="text-muted-foreground text-sm">
 Keep helper copy short. Users scan first and read second.
 </div>
 </div>
 </CardContent>
 </Card>
 </div>
 </Section>
 </>
 );
}
