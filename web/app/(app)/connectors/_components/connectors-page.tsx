"use client";

import { useState } from "react";
import { Loader2 } from "lucide-react";

import {
  connectorsByCategory,
  categoryLabels,
  type ConnectorCategory,
  type ConnectorDef,
} from "@/lib/connector-registry";
import { useConnectorsStatus } from "@/features/connectors/queries";
import { ConnectorCard } from "./connector-card";
import { ConnectorConfigSheet } from "./connector-config-sheet";

const CATEGORY_ORDER: ConnectorCategory[] = ["knowledge", "productivity", "ai"];

export function ConnectorsPage() {
  const { data, isLoading } = useConnectorsStatus();
  const [selectedConnector, setSelectedConnector] = useState<ConnectorDef | null>(null);
  const [sheetOpen, setSheetOpen] = useState(false);

  const statuses = data?.connectors ?? {};

  const handleCardClick = (connector: ConnectorDef) => {
    setSelectedConnector(connector);
    setSheetOpen(true);
  };

  const connectedCount = Object.values(statuses).filter((s) => s.connected).length;

  return (
    <div className="space-y-8">
      {/* Header */}
      <div>
        <h1 className="font-serif text-3xl tracking-tight">Connectors</h1>
        <p className="mt-1 text-muted-foreground">
          Configure your knowledge sources and integrations.
        </p>
        {!isLoading && (
          <p className="mt-2 font-mono text-xs text-muted-foreground">
            {connectedCount} connected
          </p>
        )}
      </div>

      {/* Category sections */}
      {CATEGORY_ORDER.map((category) => {
        const items = connectorsByCategory[category];
        return (
          <section key={category}>
            <h2 className="label-mono mb-4 text-[var(--alfred-text-tertiary)]">
              {categoryLabels[category]}
            </h2>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {items.map((connector) => (
                <ConnectorCard
                  key={connector.key}
                  connector={connector}
                  status={statuses[connector.key]}
                  isLoading={isLoading}
                  onClick={() => handleCardClick(connector)}
                />
              ))}
            </div>
          </section>
        );
      })}

      {/* Loading indicator */}
      {isLoading && (
        <div className="flex items-center justify-center py-8">
          <Loader2 className="size-5 animate-spin text-muted-foreground" />
        </div>
      )}

      {/* Config sheet */}
      <ConnectorConfigSheet
        connector={selectedConnector}
        status={selectedConnector ? statuses[selectedConnector.key] : undefined}
        open={sheetOpen}
        onOpenChange={setSheetOpen}
      />
    </div>
  );
}
