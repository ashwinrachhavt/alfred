"use client";

import { useEffect, useMemo, useState } from "react";
import { Loader2, Trash2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { LinkTypeCombobox } from "@/components/zettels/link-type-combobox";
import { ZettelPicker } from "@/components/zettels/zettel-picker";
import {
  useCreateZettelLink,
  useDeleteZettelLink,
  useUpdateZettelLink,
} from "@/features/zettels/mutations";
import type { ApiZettelLink } from "@/lib/api/zettels";
import { defaultBidirectional } from "@/lib/constants/zettel-link-types";

type Mode = "create" | "edit";

type Props = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  mode: Mode;
  fromCardId: number;
  initialToCardId?: number;
  initialLink?: ApiZettelLink;
  onSaved?: (link: ApiZettelLink | null) => void;
};

export function LinkEditorDialog({
  open,
  onOpenChange,
  mode,
  fromCardId,
  initialToCardId,
  initialLink,
  onSaved,
}: Props) {
  const [toCardId, setToCardId] = useState<number | null>(
    mode === "edit" ? (initialLink?.to_card_id ?? null) : (initialToCardId ?? null),
  );
  const [type, setType] = useState<string>(initialLink?.type ?? "related");
  const [context, setContext] = useState<string>(initialLink?.context ?? "");
  const [bidirectional, setBidirectional] = useState<boolean>(
    initialLink?.bidirectional ?? defaultBidirectional(initialLink?.type ?? "related"),
  );
  const [userOverrodeBidirectional, setUserOverrodeBidirectional] = useState(
    mode === "edit",
  );
  const [error, setError] = useState<string | null>(null);

  const createMutation = useCreateZettelLink(fromCardId);
  const updateMutation = useUpdateZettelLink();
  const deleteMutation = useDeleteZettelLink();
  const submitting =
    createMutation.isPending || updateMutation.isPending || deleteMutation.isPending;

  // Re-seed state whenever dialog opens to avoid stale values across reuse.
  useEffect(() => {
    if (!open) return;
    if (mode === "edit" && initialLink) {
      setToCardId(initialLink.to_card_id);
      setType(initialLink.type);
      setContext(initialLink.context ?? "");
      setBidirectional(initialLink.bidirectional);
      setUserOverrodeBidirectional(true);
    } else {
      setToCardId(initialToCardId ?? null);
      setType("related");
      setContext("");
      setBidirectional(defaultBidirectional("related"));
      setUserOverrodeBidirectional(false);
    }
    setError(null);
  }, [open, mode, initialLink, initialToCardId]);

  const onTypeChange = (next: string) => {
    setType(next);
    if (!userOverrodeBidirectional) {
      setBidirectional(defaultBidirectional(next));
    }
  };

  const submitDisabled = useMemo(() => {
    if (submitting) return true;
    if (mode === "create") {
      if (toCardId == null) return true;
      if (toCardId === fromCardId) return true;
    }
    if (!type.trim()) return true;
    return false;
  }, [submitting, mode, toCardId, fromCardId, type]);

  const handleSubmit = async () => {
    setError(null);
    try {
      if (mode === "create") {
        if (toCardId == null) return;
        const rows = await createMutation.mutateAsync({
          to_card_id: toCardId,
          type: type.trim().toLowerCase(),
          context: context.trim() || undefined,
          bidirectional,
        });
        onSaved?.(rows[0] ?? null);
      } else if (initialLink) {
        const updated = await updateMutation.mutateAsync({
          linkId: initialLink.id,
          payload: {
            type: type.trim().toLowerCase(),
            context: context.trim() ? context.trim() : null,
            bidirectional,
          },
        });
        onSaved?.(updated);
      }
      onOpenChange(false);
    } catch (err) {
      setError((err as Error).message || "Failed to save link");
    }
  };

  const handleDelete = async () => {
    if (mode !== "edit" || !initialLink) return;
    setError(null);
    try {
      await deleteMutation.mutateAsync(initialLink.id);
      onSaved?.(null);
      onOpenChange(false);
    } catch (err) {
      setError((err as Error).message || "Failed to delete link");
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>
            {mode === "create" ? "Connect this zettel" : "Edit connection"}
          </DialogTitle>
        </DialogHeader>

        <div className="flex flex-col gap-4 py-2">
          <div className="flex flex-col gap-1.5">
            <Label className="text-[10px] tracking-widest uppercase">Target zettel</Label>
            {mode === "edit" ? (
              <div className="bg-muted/40 text-muted-foreground rounded-md border px-3 py-2 text-sm">
                {`#${initialLink?.to_card_id ?? "?"}`}
              </div>
            ) : (
              <ZettelPicker
                fromCardId={fromCardId}
                value={toCardId}
                onChange={(id) => setToCardId(id)}
                autoFocus
              />
            )}
          </div>

          <div className="flex flex-col gap-1.5">
            <Label className="text-[10px] tracking-widest uppercase">Type</Label>
            <LinkTypeCombobox value={type} onChange={onTypeChange} />
          </div>

          <div className="flex items-center gap-2">
            <Checkbox
              id="link-bidirectional"
              checked={bidirectional}
              onCheckedChange={(checked) => {
                setBidirectional(Boolean(checked));
                setUserOverrodeBidirectional(true);
              }}
            />
            <Label htmlFor="link-bidirectional" className="cursor-pointer text-sm">
              Bidirectional
            </Label>
          </div>

          <div className="flex flex-col gap-1.5">
            <Label className="text-[10px] tracking-widest uppercase">
              Context (optional)
            </Label>
            <Textarea
              value={context}
              onChange={(e) => setContext(e.target.value)}
              placeholder="Why are these related?"
              rows={3}
              className="text-sm"
            />
          </div>

          {error && (
            <div className="text-destructive text-xs" role="alert">
              {error}
            </div>
          )}
        </div>

        <DialogFooter className="flex items-center justify-between gap-2 sm:justify-between">
          <div>
            {mode === "edit" && (
              <Button
                type="button"
                variant="ghost"
                size="sm"
                onClick={handleDelete}
                disabled={submitting}
                className="text-muted-foreground hover:text-destructive"
              >
                <Trash2 size={14} className="mr-1" />
                Delete
              </Button>
            )}
          </div>
          <div className="flex items-center gap-2">
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={() => onOpenChange(false)}
              disabled={submitting}
            >
              Cancel
            </Button>
            <Button
              type="button"
              size="sm"
              onClick={handleSubmit}
              disabled={submitDisabled}
            >
              {submitting && <Loader2 size={12} className="mr-1 animate-spin" />}
              {mode === "create" ? "Connect" : "Save"}
            </Button>
          </div>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
