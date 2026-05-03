import Link from "next/link";

import { Page } from "@/components/layout/page";
import { ThemeToggle } from "@/components/theme-toggle";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

import { ComponentsTab } from "./_components/components-tab";
import { FoundationsTab } from "./_components/foundations-tab";
import { PatternsTab } from "./_components/patterns-tab";

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
 A living reference for Polymath’s UI foundations, components, and usage guidelines.
 </p>
 <div className="text-muted-foreground flex flex-wrap items-center gap-2 text-xs">
 <span className="bg-muted/30 rounded-full border px-3 py-1">Semantic tokens</span>
 <span className="bg-muted/30 rounded-full border px-3 py-1">Radix primitives</span>
 <span className="bg-muted/30 rounded-full border px-3 py-1">Tailwind v4</span>
 </div>
 </div>

 <div className="flex items-center gap-2">
 <Button asChild variant="outline" size="sm">
 <Link href="/">Back to app</Link>
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
 <FoundationsTab />
 </TabsContent>

 <TabsContent value="components" className="mt-6 space-y-8">
 <ComponentsTab />
 </TabsContent>

 <TabsContent value="patterns" className="mt-6 space-y-8">
 <PatternsTab />
 </TabsContent>
 </Tabs>
 </div>
 </Page>
 );
}
