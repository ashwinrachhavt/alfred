"use client";

import { VisuallyHidden } from "@radix-ui/react-visually-hidden";

import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/components/ui/dialog";
import { ZettelFullView } from "./zettel-full-view";

type Props = {
  cardId: number | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
};

export function ZettelFullViewDialog({ cardId, open, onOpenChange }: Props) {
  if (cardId === null) return null;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        className="h-[min(88vh,920px)] max-w-[min(1180px,calc(100vw-2rem))] gap-0 overflow-hidden p-0"
      >
        <VisuallyHidden>
          <DialogTitle>Expanded zettel view</DialogTitle>
          <DialogDescription>
            Review the full zettel content, metadata, and AI link suggestions without leaving the current page.
          </DialogDescription>
        </VisuallyHidden>
        <ZettelFullView zettelId={cardId} variant="dialog" />
      </DialogContent>
    </Dialog>
  );
}
