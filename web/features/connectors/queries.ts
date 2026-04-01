import { useQuery } from "@tanstack/react-query";
import { apiRoutes } from "@/lib/api/routes";

export type ConnectorStatus = {
  connected: boolean;
  auth_type: "oauth" | "api_key" | "none" | "unknown";
  details?: Record<string, unknown>;
  error?: string;
};

export type ConnectorsStatusAll = {
  connectors: Record<string, ConnectorStatus>;
};

async function fetchConnectorsStatusAll(): Promise<ConnectorsStatusAll> {
  const res = await fetch(apiRoutes.connectors.statusAll);
  if (!res.ok) throw new Error(`Failed to fetch connector statuses: ${res.status}`);
  return res.json();
}

export function useConnectorsStatus() {
  return useQuery({
    queryKey: ["connectors", "status-all"],
    queryFn: fetchConnectorsStatusAll,
    staleTime: 600_000,
    refetchOnWindowFocus: true,
  });
}
