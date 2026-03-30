import Link from "next/link";

import { Page } from "@/components/layout/page";
import { ThemeToggle } from "@/components/theme-toggle";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
 Dialog,
 DialogContent,
 DialogDescription,
 DialogFooter,
 DialogHeader,
 DialogTitle,
 DialogTrigger,
} from "@/components/ui/dialog";
import { EmptyState } from "@/components/ui/empty-state";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";
import { Switch } from "@/components/ui/switch";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

type TokenSwatchProps = {
 name: string;
 className: string;
 description?: string;
};

function TokenSwatch({ name, className, description }: TokenSwatchProps) {
 return (
 <div className="flex items-center justify-between gap-4 rounded-xl border p-4">
 <div className="space-y-1">
 <div className="flex flex-wrap items-center gap-2">
 <code className="bg-muted/40 rounded-md px-2 py-1 text-xs">{name}</code>
 {description ? (
 <span className="text-muted-foreground text-xs">{description}</span>
 ) : null}
 </div>
 </div>
 <div className={`h-10 w-16 rounded-lg border shadow-xs ${className}`} aria-hidden="true" />
 </div>
 );
}

function Section({
 title,
 description,
 children,
}: {
 title: string;
 description?: string;
 children: React.ReactNode;
}) {
 return (
 <section className="space-y-4">
 <div className="space-y-1">
 <h2 className="text-xl font-semibold tracking-tight">{title}</h2>
 {description ? <p className="text-muted-foreground text-sm">{description}</p> : null}
 </div>
 {children}
 </section>
 );
}

export default function DesignSystemPage() {
 return (
 <Page size="wide" className="py-10">
 <div className="space-y-8">
 <header className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
 <div className="space-y-2">
 <div className="flex flex-wrap items-center gap-2">
 <h1 className="text-3xl font-semibold tracking-tight">Design System</h1>
 <Badge variant="secondary">Internal</Badge>
 </div>
 <p className="text-muted-foreground max-w-2xl text-sm">
 A living reference for Alfred’s UI foundations, components, and usage guidelines.
 </p>
 <div className="text-muted-foreground flex flex-wrap items-center gap-2 text-xs">
 <span className="bg-muted/30 rounded-full border px-3 py-1">Semantic tokens</span>
 <span className="bg-muted/30 rounded-full border px-3 py-1">Radix primitives</span>
 <span className="bg-muted/30 rounded-full border px-3 py-1">Tailwind v4</span>
 </div>
 </div>

 <div className="flex items-center gap-2">
 <Button asChild variant="outline" size="sm">
 <Link href="/">{`Back to app`}</Link>
 </Button>
 <ThemeToggle />
 </div>
 </header>

 <Tabs defaultValue="foundations">
 <TabsList>
 <TabsTrigger value="foundations">Foundations</TabsTrigger>
 <TabsTrigger value="components">Components</TabsTrigger>
 <TabsTrigger value="patterns">Patterns</TabsTrigger>
 </TabsList>

 <TabsContent value="foundations" className="mt-6 space-y-8">
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
 </TabsContent>

 <TabsContent value="components" className="mt-6 space-y-8">
 <Section title="Buttons" description="Variants and sizes are standardized via CVA.">
 <Card>
 <CardContent className="space-y-5 pt-6">
 <div className="flex flex-wrap gap-3">
 <Button>Primary</Button>
 <Button variant="secondary">Secondary</Button>
 <Button variant="outline">Outline</Button>
 <Button variant="ghost">Ghost</Button>
 <Button variant="link">Link</Button>
 <Button variant="destructive">Destructive</Button>
 </div>
 <Separator />
 <div className="flex flex-wrap items-center gap-3">
 <Button size="sm" variant="outline">
 Small
 </Button>
 <Button size="default" variant="outline">
 Default
 </Button>
 <Button size="lg" variant="outline">
 Large
 </Button>
 </div>
 </CardContent>
 </Card>
 </Section>

 <Section
 title="Form controls"
 description="Always pair inputs with labels and visible focus."
 >
 <Card>
 <CardContent className="space-y-6 pt-6">
 <div className="grid gap-4 md:grid-cols-2">
 <div className="space-y-2">
 <Label htmlFor="ds-input">Text input</Label>
 <Input id="ds-input" placeholder="Search, name, or command…" />
 </div>
 <div className="flex items-center justify-between rounded-lg border p-4">
 <div className="space-y-1">
 <div className="text-sm font-medium">Toggle</div>
 <div className="text-muted-foreground text-xs">
 Use for binary preferences.
 </div>
 </div>
 <Switch aria-label="Example toggle" />
 </div>
 </div>
 </CardContent>
 </Card>
 </Section>

 <Section
 title="Dialogs"
 description="Use for focused tasks; keep them short and scannable."
 >
 <Card>
 <CardContent className="pt-6">
 <Dialog>
 <DialogTrigger asChild>
 <Button variant="outline">Open example dialog</Button>
 </DialogTrigger>
 <DialogContent>
 <DialogHeader>
 <DialogTitle>Confirm action</DialogTitle>
 <DialogDescription>
 Dialogs are for short, focused flows. Avoid turning them into full pages.
 </DialogDescription>
 </DialogHeader>
 <DialogFooter>
 <Button variant="outline" type="button">
 Cancel
 </Button>
 <Button type="button">Continue</Button>
 </DialogFooter>
 </DialogContent>
 </Dialog>
 </CardContent>
 </Card>
 </Section>
 </TabsContent>

 <TabsContent value="patterns" className="mt-6 space-y-8">
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
 </TabsContent>
 </Tabs>
 </div>
 </Page>
 );
}
