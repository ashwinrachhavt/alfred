import type { ReactNode } from "react";

type TokenSwatchProps = {
 name: string;
 className: string;
 description?: string;
};

export function TokenSwatch({ name, className, description }: TokenSwatchProps) {
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

export function Section({
 title,
 description,
 children,
}: {
 title: string;
 description?: string;
 children: ReactNode;
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
