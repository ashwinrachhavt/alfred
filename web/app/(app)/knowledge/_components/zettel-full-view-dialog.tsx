"use client";

import { VisuallyHidden } from "@radix-ui/react-visually-hidden";
import { X } from "lucide-react";

import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogTitle,
} from "@/components/ui/dialog";
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
        showCloseButton={false}
        className="bg-background h-[100dvh] max-h-[100dvh] w-[100dvw] max-w-none gap-0 overflow-hidden rounded-none border-0 p-0 shadow-2xl sm:h-[min(92dvh,940px)] sm:w-[calc(100vw-2rem)] sm:max-w-[min(1240px,calc(100vw-2rem))] sm:rounded-xl sm:border"
      >
        <VisuallyHidden>
          <DialogTitle>Expanded zettel view</DialogTitle>
          <DialogDescription>
            Review the full zettel content, metadata, and AI link suggestions without leaving the
            current page.
          </DialogDescription>
        </VisuallyHidden>
        <DialogClose className="bg-card/95 text-muted-foreground hover:border-primary/40 hover:bg-accent hover:text-foreground focus-visible:ring-ring absolute top-3 right-3 z-20 inline-flex size-9 items-center justify-center rounded-md border shadow-sm transition-colors focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:outline-none sm:top-4 sm:right-4">
          <X className="size-4" />
          <span className="sr-only">Close</span>
        </DialogClose>
        <ZettelFullView zettelId={cardId} variant="dialog" />
      </DialogContent>
    </Dialog>
  );
}
