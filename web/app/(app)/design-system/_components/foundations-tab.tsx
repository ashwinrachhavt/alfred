import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

import { Section, TokenSwatch } from "./primitives";

export function FoundationsTab() {
 return (
 <>
 <Section
 title="Color tokens"
 description="Prefer semantic utilities (bg-background, text-foreground, border-border) over raw colors."
 >
 <div className="grid gap-3 md:grid-cols-2">
 <TokenSwatch name="bg-background" className="bg-background" />
 <TokenSwatch name="bg-card" className="bg-card" />
 <TokenSwatch name="bg-popover" className="bg-popover" />
 <TokenSwatch name="bg-primary" className="bg-primary" />
 <TokenSwatch name="bg-secondary" className="bg-secondary" />
 <TokenSwatch name="bg-accent" className="bg-accent" />
 <TokenSwatch name="bg-destructive" className="bg-destructive" />
 <TokenSwatch
 name="border-border"
 className="bg-border"
 description="Border color"
 />
 </div>
 <p className="text-muted-foreground text-sm">
 Source of truth:{" "}
 <code className="bg-muted/40 rounded px-1.5 py-0.5">web/app/globals.css</code>.
 See{" "}
 <code className="bg-muted/40 rounded px-1.5 py-0.5">
 web/docs/design-system-bible.md
 </code>{" "}
 for how to add tokens.
 </p>
 </Section>

 <Section
 title="Typography"
 description="Use the existing scale and keep hierarchy clear."
 >
 <Card>
 <CardHeader>
 <CardTitle className="text-base">Type scale</CardTitle>
 </CardHeader>
 <CardContent className="space-y-3">
 <div className="space-y-1">
 <div className="text-4xl font-semibold tracking-tight">Heading 1</div>
 <div className="text-muted-foreground text-xs">
 text-4xl font-semibold tracking-tight
 </div>
 </div>
 <div className="space-y-1">
 <div className="text-2xl font-semibold tracking-tight">Heading 2</div>
 <div className="text-muted-foreground text-xs">
 text-2xl font-semibold tracking-tight
 </div>
 </div>
 <div className="space-y-1">
 <div className="text-base">
 Body text should be readable, calm, and avoid unnecessary emphasis.
 </div>
 <div className="text-muted-foreground text-xs">text-base</div>
 </div>
 <div className="space-y-1">
 <div className="text-muted-foreground text-sm">
 Secondary text uses muted foreground to reduce visual noise.
 </div>
 <div className="text-muted-foreground text-xs">
 text-sm text-muted-foreground
 </div>
 </div>
 </CardContent>
 </Card>
 </Section>

 <Section
 title="Radius"
 description="Roundness is tokenized; keep it consistent across UI."
 >
 <div className="grid gap-4 sm:grid-cols-3">
 <div className="space-y-2 rounded-xl border p-4">
 <div className="bg-muted/30 h-12 w-full rounded-sm" />
 <div className="text-xs">
 <code className="bg-muted/40 rounded px-1.5 py-0.5">rounded-sm</code>
 </div>
 </div>
 <div className="space-y-2 rounded-xl border p-4">
 <div className="bg-muted/30 h-12 w-full rounded-lg" />
 <div className="text-xs">
 <code className="bg-muted/40 rounded px-1.5 py-0.5">rounded-lg</code>
 </div>
 </div>
 <div className="space-y-2 rounded-xl border p-4">
 <div className="bg-muted/30 h-12 w-full rounded-3xl" />
 <div className="text-xs">
 <code className="bg-muted/40 rounded px-1.5 py-0.5">rounded-3xl</code>{" "}
 <span className="text-muted-foreground">for hero surfaces</span>
 </div>
 </div>
 </div>
 </Section>
 </>
 );
}
