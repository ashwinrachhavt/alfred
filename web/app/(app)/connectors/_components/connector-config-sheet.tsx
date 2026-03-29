"use client";

import { useState } from "react";
import { Eye, EyeOff, ExternalLink, Loader2, Unlink } from "lucide-react";
import { toast } from "sonner";
import { useQueryClient } from "@tanstack/react-query";

import type { ConnectorDef } from "@/lib/connector-registry";
import type { ConnectorStatus } from "@/features/connectors/queries";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";

type Props = {
  connector: ConnectorDef | null;
  status: ConnectorStatus | undefined;
  open: boolean;
  onOpenChange: (open: boolean) => void;
};

const OAUTH_CONNECTORS: Record<string, { authUrlEndpoint: string; label: string }> = {
  notion: { authUrlEndpoint: "/api/notion/auth_url", label: "Notion" },
  gmail: { authUrlEndpoint: "/api/gmail/auth_url", label: "Gmail" },
  calendar: { authUrlEndpoint: "/api/calendar/auth_url", label: "Google Calendar" },
  gdrive: { authUrlEndpoint: "/api/gdrive/auth_url", label: "Google Drive" },
  google_tasks: { authUrlEndpoint: "/api/google_tasks/auth_url", label: "Google Tasks" },
};

export function ConnectorConfigSheet({ connector, status, open, onOpenChange }: Props) {
  const queryClient = useQueryClient();
  const [apiKey, setApiKey] = useState("");
  const [showKey, setShowKey] = useState(false);
  const [isConnecting, setIsConnecting] = useState(false);

  if (!connector) return null;

  const Icon = connector.icon;
  const isConnected = status?.connected ?? false;

  const handleOAuthConnect = async () => {
    const oauth = OAUTH_CONNECTORS[connector.key];
    if (!oauth) return;
    setIsConnecting(true);
    try {
      const res = await fetch(oauth.authUrlEndpoint);
      if (!res.ok) throw new Error("Failed to get auth URL");
      const data = await res.json();
      window.location.href = data.authorization_url;
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "OAuth failed");
      setIsConnecting(false);
    }
  };

  const handleApiKeySave = async () => {
    if (!apiKey.trim()) return;
    toast.info("API key saving is not yet implemented — set it in your .env file for now.");
    setApiKey("");
  };

  const handleDisconnect = async () => {
    toast.info("Disconnect is available per-connector — use the existing connector page for now.");
    void queryClient.invalidateQueries({ queryKey: ["connectors"] });
  };

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent className="w-[380px] sm:w-[420px]">
        <SheetHeader>
          <div className="flex items-center gap-3">
            <div className="flex size-10 items-center justify-center rounded-md bg-muted">
              <Icon className="size-5" />
            </div>
            <div>
              <SheetTitle className="text-left">{connector.label}</SheetTitle>
              <SheetDescription className="text-left">
                {connector.description}
              </SheetDescription>
            </div>
          </div>
        </SheetHeader>

        <div className="mt-6 space-y-6">
          {/* Status */}
          <div className="flex items-center justify-between rounded-lg border p-3">
            <span className="font-mono text-xs uppercase tracking-wider text-muted-foreground">
              Status
            </span>
            <Badge variant={isConnected ? "default" : "secondary"}>
              {isConnected ? "Connected" : "Not connected"}
            </Badge>
          </div>

          {/* Auth section */}
          {connector.authType === "oauth" && (
            <div className="space-y-3">
              <Label className="font-mono text-xs uppercase tracking-wider">
                Authentication
              </Label>
              {isConnected ? (
                <div className="space-y-2">
                  <p className="text-sm text-muted-foreground">
                    Connected via OAuth.
                  </p>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => void handleDisconnect()}
                    className="text-destructive"
                  >
                    <Unlink className="mr-2 size-3.5" />
                    Disconnect
                  </Button>
                </div>
              ) : (
                <Button
                  onClick={() => void handleOAuthConnect()}
                  disabled={isConnecting || !OAUTH_CONNECTORS[connector.key]}
                  size="sm"
                >
                  {isConnecting && <Loader2 className="mr-2 size-3.5 animate-spin" />}
                  {OAUTH_CONNECTORS[connector.key]
                    ? `Connect ${connector.label}`
                    : "OAuth not configured"}
                </Button>
              )}
            </div>
          )}

          {connector.authType === "api_key" && (
            <div className="space-y-3">
              <Label className="font-mono text-xs uppercase tracking-wider">
                API Key
              </Label>
              {isConnected ? (
                <div className="space-y-2">
                  <p className="text-sm text-muted-foreground">
                    API key configured via environment variable.
                  </p>
                  <Badge variant="outline" className="text-[10px]">
                    Set in .env
                  </Badge>
                </div>
              ) : (
                <div className="space-y-2">
                  <div className="relative">
                    <Input
                      type={showKey ? "text" : "password"}
                      placeholder="Enter API key..."
                      value={apiKey}
                      onChange={(e) => setApiKey(e.target.value)}
                      className="pr-10 font-mono text-xs"
                    />
                    <button
                      type="button"
                      onClick={() => setShowKey(!showKey)}
                      className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                    >
                      {showKey ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
                    </button>
                  </div>
                  <Button
                    size="sm"
                    onClick={() => void handleApiKeySave()}
                    disabled={!apiKey.trim()}
                  >
                    Save Key
                  </Button>
                  <p className="text-xs text-muted-foreground">
                    Or set the key in your <code className="text-[10px]">.env</code> file.
                  </p>
                </div>
              )}
            </div>
          )}

          {connector.authType === "none" && (
            <div className="space-y-2">
              <Label className="font-mono text-xs uppercase tracking-wider">
                Authentication
              </Label>
              <p className="text-sm text-muted-foreground">
                No authentication required. This connector uses open APIs.
              </p>
            </div>
          )}

          {/* Metadata */}
          <div className="space-y-2 border-t pt-4">
            <div className="flex items-center justify-between text-xs">
              <span className="text-muted-foreground">Auth type</span>
              <span className="font-mono">{connector.authType}</span>
            </div>
            <div className="flex items-center justify-between text-xs">
              <span className="text-muted-foreground">Content type</span>
              <span className="font-mono">{connector.contentType}</span>
            </div>
            <div className="flex items-center justify-between text-xs">
              <span className="text-muted-foreground">Backend</span>
              <span className="font-mono">{connector.hasBackend ? "Available" : "Planned"}</span>
            </div>
          </div>
        </div>
      </SheetContent>
    </Sheet>
  );
}
