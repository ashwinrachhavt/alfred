import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import {
 Dialog,
 DialogContent,
 DialogDescription,
 DialogFooter,
 DialogHeader,
 DialogTitle,
 DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";
import { Switch } from "@/components/ui/switch";

import { Section } from "./primitives";

export function ComponentsTab() {
 return (
 <>
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
 </>
 );
}
