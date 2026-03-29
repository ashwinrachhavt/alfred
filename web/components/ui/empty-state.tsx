import * as React from "react";

import { cn } from "@/lib/utils";

export type EmptyStateProps = {
 title: string;
 description?: string;
 icon?: React.ComponentType<{ className?: string }>;
 action?: React.ReactNode;
 className?: string;
};

export function EmptyState({ title, description, icon: Icon, action, className }: EmptyStateProps) {
 return (
 <div
 className={cn("flex flex-col items-center justify-center gap-3 py-10 text-center", className)}
 >
 {Icon ? (
 <div className="bg-muted text-muted-foreground flex h-10 w-10 items-center justify-center rounded-xl">
 <Icon className="h-5 w-5" aria-hidden="true" />
 </div>
 ) : null}
 <div className="space-y-1">
 <p className="text-sm font-medium">{title}</p>
 {description ? <p className="text-muted-foreground text-sm">{description}</p> : null}
 </div>
 {action ? <div className="pt-1">{action}</div> : null}
 </div>
 );
}
