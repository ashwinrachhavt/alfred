import { cn } from "@/lib/utils";

export type PageProps = {
 children: React.ReactNode;
 className?: string;
 /**
 * Controls the maximum readable width for the page content.
 */
 size?: "full" | "wide" | "default" | "comfortable" | "narrow";
};

const sizeClasses: Record<NonNullable<PageProps["size"]>, string> = {
 full: "max-w-none",
 wide: "max-w-7xl",
 default: "max-w-6xl",
 comfortable: "max-w-5xl",
 narrow: "max-w-4xl",
};

/**
 * Consistent page container used across the app.
 */
export function Page({ children, className, size = "default" }: PageProps) {
 return (
 <div className={cn("mx-auto w-full px-6 py-8", sizeClasses[size], className)}>{children}</div>
 );
}
