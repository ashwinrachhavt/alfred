"use client";

import { useMemo, useState } from "react";
import { RefreshCcw, Share2 } from "lucide-react";
import { toast } from "sonner";

import { updateSystemDesignShareSettings } from "@/lib/api/system-design";
import type { SystemDesignSession } from "@/lib/api/types/system-design";

import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";

type ExpiryPreset = "never" | "1d" | "7d" | "30d";

function computeExpiryIso(preset: ExpiryPreset): string | null {
  const now = Date.now();
  switch (preset) {
    case "never":
      return null;
    case "1d":
      return new Date(now + 24 * 60 * 60 * 1000).toISOString();
    case "7d":
      return new Date(now + 7 * 24 * 60 * 60 * 1000).toISOString();
    case "30d":
      return new Date(now + 30 * 24 * 60 * 60 * 1000).toISOString();
  }
}

function toExpiryPreset(expiresAt: string | null): ExpiryPreset | "custom" {
  if (!expiresAt) return "never";
  const deltaMs = Date.parse(expiresAt) - Date.now();
  const deltaDays = Math.round(deltaMs / (24 * 60 * 60 * 1000));
  if (deltaDays <= 1) return "1d";
  if (deltaDays <= 7) return "7d";
  if (deltaDays <= 30) return "30d";
  return "custom";
}

export function SystemDesignShareDialog({
  session,
  onSessionUpdated,
}: {
  session: SystemDesignSession;
  onSessionUpdated: (next: SystemDesignSession) => void;
}) {
  const [open, setOpen] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [password, setPassword] = useState("");

  const origin = typeof window !== "undefined" ? window.location.origin : "";
  const sharePath = `/system-design/share/${session.share_id}`;
  const shareUrl = origin ? `${origin}${sharePath}` : sharePath;
  const embedUrl = `${shareUrl}?embed=1`;
  const embedSnippet = `<iframe src="${embedUrl}" width="100%" height="600" style="border:1px solid #e5e7eb;border-radius:12px;" loading="lazy"></iframe>`;

  const expiryPreset = useMemo(
    () => toExpiryPreset(session.share_settings.expires_at),
    [session.share_settings.expires_at],
  );

  async function applyShareUpdate(update: Parameters<typeof updateSystemDesignShareSettings>[1]) {
    setIsSaving(true);
    try {
      const next = await updateSystemDesignShareSettings(session.id, update);
      onSessionUpdated(next);
      toast.success("Share settings updated");
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to update share settings.";
      toast.error(message);
    } finally {
      setIsSaving(false);
    }
  }

  async function copy(text: string, label: string) {
    try {
      await navigator.clipboard.writeText(text);
      toast.success(`${label} copied`);
    } catch {
      toast.error("Copy failed");
    }
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button variant="outline" size="icon-sm" aria-label="Share diagram">
          <Share2 className="size-4" />
        </Button>
      </DialogTrigger>

      <DialogContent className="sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>Share</DialogTitle>
          <DialogDescription>
            Share a read-only link. Optional password and expiry are enforced server-side.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-6">
          <div className="flex items-start justify-between gap-6">
            <div className="space-y-1">
              <Label htmlFor="sdShareEnabled">Share link active</Label>
              <p className="text-muted-foreground text-xs">
                Disable to invalidate the public view without rotating the URL.
              </p>
            </div>
            <Switch
              id="sdShareEnabled"
              checked={session.share_settings.enabled}
              onCheckedChange={(checked) => void applyShareUpdate({ enabled: checked })}
              disabled={isSaving}
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="sdShareLink">Share link</Label>
            <div className="flex gap-2">
              <Input id="sdShareLink" value={shareUrl} readOnly />
              <Button type="button" variant="outline" onClick={() => void copy(shareUrl, "Link")}>
                Copy
              </Button>
              <Button
                type="button"
                variant="outline"
                onClick={() => void applyShareUpdate({ rotate_share_id: true })}
                disabled={isSaving}
                title="Regenerate link"
              >
                <RefreshCcw className="mr-2 size-4" />
                Rotate
              </Button>
            </div>
          </div>

          <div className="space-y-2">
            <Label htmlFor="sdEmbed">Embed</Label>
            <Textarea id="sdEmbed" value={embedSnippet} readOnly rows={3} className="resize-none" />
            <div className="flex gap-2">
              <Button type="button" variant="outline" onClick={() => void copy(embedSnippet, "Embed snippet")}>
                Copy snippet
              </Button>
              <Button type="button" variant="outline" onClick={() => void copy(embedUrl, "Embed URL")}>
                Copy URL
              </Button>
            </div>
          </div>

          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-2">
              <Label>Expiry</Label>
              <Select
                value={expiryPreset === "custom" ? "custom" : expiryPreset}
                onValueChange={(value) => {
                  if (value === "custom") return;
                  void applyShareUpdate({ expires_at: computeExpiryIso(value as ExpiryPreset) });
                }}
                disabled={isSaving}
              >
                <SelectTrigger>
                  <SelectValue placeholder="Select expiry" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="never">Never</SelectItem>
                  <SelectItem value="1d">24 hours</SelectItem>
                  <SelectItem value="7d">7 days</SelectItem>
                  <SelectItem value="30d">30 days</SelectItem>
                  <SelectItem value="custom" disabled>
                    Custom
                  </SelectItem>
                </SelectContent>
              </Select>
              {expiryPreset === "custom" && session.share_settings.expires_at ? (
                <p className="text-muted-foreground text-xs">
                  Current expiry: {new Date(session.share_settings.expires_at).toLocaleString()}
                </p>
              ) : null}
            </div>

            <div className="space-y-2">
              <Label>Password</Label>
              <Input
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder={session.share_settings.has_password ? "Set new password…" : "Set a password…"}
                disabled={isSaving}
              />
              <div className="flex gap-2">
                <Button
                  type="button"
                  onClick={() => void applyShareUpdate({ password })}
                  disabled={isSaving || !password.trim()}
                >
                  Set
                </Button>
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => void applyShareUpdate({ clear_password: true })}
                  disabled={isSaving || !session.share_settings.has_password}
                >
                  Clear
                </Button>
              </div>
              <p className="text-muted-foreground text-xs">
                {session.share_settings.has_password ? "Password is required to view." : "No password required."}
              </p>
            </div>
          </div>
        </div>

        <DialogFooter>
          <Button type="button" variant="outline" onClick={() => setOpen(false)}>
            Done
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

