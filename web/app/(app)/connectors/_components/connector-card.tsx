"use client";

import { cn } from "@/lib/utils";
import type { ConnectorDef } from "@/lib/connector-registry";
import type { ConnectorStatus } from "@/features/connectors/queries";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";

type Props = {
  connector: ConnectorDef;
  status: ConnectorStatus | undefined;
  isLoading: boolean;
  onClick: () => void;
};

function statusLabel(status: ConnectorStatus | undefined, authType: string, isLoading: boolean) {
  if (isLoading) return { text: "Checking...", variant: "secondary" as const };
  if (!status) return { text: "Unknown", variant: "secondary" as const };
  if (status.error) return { text: "Error", variant: "destructive" as const };
  if (status.connected) return { text: "Connected", variant: "default" as const };
  if (authType === "none") return { text: "Ready", variant: "outline" as const };
  return { text: "Not connected", variant: "secondary" as const };
}

export function ConnectorCard({ connector, status, isLoading, onClick }: Props) {
  const Icon = connector.icon;
  const badge = statusLabel(status, connector.authType, isLoading);

  return (
    <Card
      className={cn(
        "group cursor-pointer transition-all hover:border-primary/30 hover:shadow-sm",
        status?.connected && "border-[var(--color-success)]/20",
      )}
      onClick={onClick}
    >
      <CardContent className="flex items-start gap-3 p-4">
        <div className="flex size-10 shrink-0 items-center justify-center rounded-md bg-muted">
          <Icon className="size-5 text-muted-foreground group-hover:text-foreground transition-colors" />
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex items-center justify-between gap-2">
            <span className="font-mono text-sm font-medium tracking-wide">
              {connector.label}
            </span>
            <Badge variant={badge.variant} className="shrink-0 text-[10px]">
              {badge.text}
            </Badge>
          </div>
          <p className="mt-1 text-xs text-muted-foreground line-clamp-2">
            {connector.description}
          </p>
        </div>
      </CardContent>
    </Card>
  );
}
