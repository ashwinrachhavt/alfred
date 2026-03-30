"use client";

import { useState } from "react";
import { Loader2, Link2, Unlink, ExternalLink } from "lucide-react";
import { toast } from "sonner";
import { useQueryClient } from "@tanstack/react-query";

import { useNotionStatus } from "@/features/notion/queries";
import { getNotionAuthUrl, revokeNotionWorkspace } from "@/lib/api/notion";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export function NotionConnect() {
 const queryClient = useQueryClient();
 const statusQuery = useNotionStatus();
 const [isConnecting, setIsConnecting] = useState(false);

 const status = statusQuery.data;
 const isConnected =
 (status?.env_token_present ?? false) ||
 (status?.connected_workspaces?.length ?? 0) > 0;

 const handleConnect = async () => {
 setIsConnecting(true);
 try {
 const { authorization_url } = await getNotionAuthUrl();
 window.location.href = authorization_url;
 } catch (err) {
 toast.error(err instanceof Error ? err.message : "Failed to start Notion OAuth.");
 setIsConnecting(false);
 }
 };

 const handleDisconnect = async (workspaceId: string) => {
 try {
 await revokeNotionWorkspace(workspaceId);
 toast.success("Disconnected from Notion workspace.");
 void queryClient.invalidateQueries({ queryKey: ["notion"] });
 } catch (err) {
 toast.error(err instanceof Error ? err.message : "Failed to disconnect.");
 }
 };

 return (
 <Card>
 <CardHeader>
 <div className="flex items-center justify-between">
 <CardTitle className="flex items-center gap-2">
 <svg className="h-5 w-5" viewBox="0 0 100 100" fill="none">
 <path
 d="M6.017 4.313l55.333-4.08c6.797-.583 8.543-.19 12.817 2.917l17.663 12.443c2.913 2.14 3.883 2.723 3.883 5.053v68.243c0 4.277-1.553 6.807-6.99 7.193L24.467 99.967c-4.08.193-6.023-.39-8.16-3.113L3.3 79.94c-2.333-3.113-3.3-5.443-3.3-8.167V11.113c0-3.497 1.553-6.413 6.017-6.8z"
 fill="currentColor"
 />
 <path
 d="M61.35.233l-55.333 4.08C.553 4.7 0 7.617 0 11.113v60.66c0 2.724.967 5.054 3.3 8.167l13.007 16.913c2.137 2.723 4.08 3.307 8.16 3.113l64.257-3.89c5.433-.386 6.99-2.916 6.99-7.193V20.64c0-2.21-.873-2.847-3.443-4.733L74.167 3.15C69.893.233 68.147-.36 61.35.233zM25.505 19.76c-5.18.305-6.355.374-9.305-1.996L8.893 11.86c-.783-.78-.387-1.753 1.167-1.946l52.33-3.8c4.467-.39 6.8 1.167 8.543 2.53l9.11 6.607c.387.194.967 1.167.193 1.167l-54.15 3.15-.58.193zM19.523 85.06V33.437c0-2.527.773-3.697 3.113-3.893l58.937-3.397c2.14-.193 3.107 1.167 3.107 3.693v51.047c0 2.53-.39 4.667-3.887 4.86l-56.43 3.303c-3.497.193-4.84-1.003-4.84-3.95zM74.87 37.523c.387 1.75 0 3.5-1.75 3.7l-2.723.517v37.81c-2.333 1.167-4.473 1.944-6.22 1.944-2.917 0-3.7-.967-5.833-3.507L40.787 52.657v23.063l5.637 1.363s0 3.5-4.857 3.5l-13.393.773c-.387-.773 0-1.943 1.167-2.333l3.5-.967V44.327l-4.857-.393c-.387-1.75.583-4.277 3.3-4.473l14.367-.967 18.467 28.237V44.523l-4.857-.58c-.387-2.14 1.167-3.693 3.107-3.887l13.4-.533z"
 fill="white"
 />
 </svg>
 Notion Connection
 </CardTitle>
 <Badge variant={isConnected ? "default" : "secondary"}>
 {statusQuery.isLoading
 ? "Checking..."
 : isConnected
 ? "Connected"
 : "Not connected"}
 </Badge>
 </div>
 </CardHeader>
 <CardContent className="space-y-4">
 {statusQuery.isError && (
 <Alert variant="destructive">
 <AlertDescription>Failed to check Notion status.</AlertDescription>
 </Alert>
 )}

 {status?.oauth_error && (
 <Alert variant="destructive">
 <AlertDescription>{status.oauth_error}</AlertDescription>
 </Alert>
 )}

 {isConnected && status?.connected_workspaces?.length ? (
 <div className="space-y-3">
 {status.connected_workspaces.map((ws) => (
 <div
 key={ws.workspace_id}
 className="flex items-center justify-between rounded-lg border p-3"
 >
 <div className="space-y-0.5">
 <p className="font-medium">
 {ws.workspace_name ?? ws.workspace_id}
 </p>
 <p className="text-muted-foreground text-xs">
 {ws.workspace_id}
 </p>
 </div>
 <Button
 size="sm"
 variant="ghost"
 onClick={() => void handleDisconnect(ws.workspace_id)}
 >
 <Unlink className="mr-2 h-4 w-4" />
 Disconnect
 </Button>
 </div>
 ))}
 </div>
 ) : isConnected && status?.env_token_present ? (
 <p className="text-muted-foreground text-sm">
 Using server-configured integration token (NOTION_TOKEN).
 </p>
 ) : null}

 {!isConnected && (
 <div className="space-y-3">
 <p className="text-muted-foreground text-sm">
 Connect your Notion workspace to search pages, read content, and sync
 knowledge into Alfred.
 </p>
 {!status?.oauth_configured && (
 <Alert>
 <AlertDescription>
 OAuth is not configured on the backend. Set{" "}
 <code className="text-xs">NOTION_CLIENT_ID</code>,{" "}
 <code className="text-xs">NOTION_CLIENT_SECRET</code>, and{" "}
 <code className="text-xs">NOTION_REDIRECT_URI</code> in your .env.
 </AlertDescription>
 </Alert>
 )}
 </div>
 )}

 <div className="flex gap-2">
 <Button
 onClick={() => void handleConnect()}
 disabled={isConnecting || !status?.oauth_configured}
 >
 {isConnecting ? (
 <Loader2 className="mr-2 h-4 w-4 animate-spin" />
 ) : (
 <Link2 className="mr-2 h-4 w-4" />
 )}
 {isConnected ? "Connect another workspace" : "Connect Notion"}
 </Button>
 {isConnected && (
 <Button
 variant="outline"
 asChild
 >
 <a
 href="https://www.notion.so"
 target="_blank"
 rel="noreferrer"
 >
 <ExternalLink className="mr-2 h-4 w-4" />
 Open Notion
 </a>
 </Button>
 )}
 </div>
 </CardContent>
 </Card>
 );
}
