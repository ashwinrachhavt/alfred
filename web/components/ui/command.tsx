"use client";

import * as React from "react";
import * as DialogPrimitive from "@radix-ui/react-dialog";
import { Command as CommandPrimitive } from "cmdk";
import { Search } from "lucide-react";

import { cn } from "@/lib/utils";
import { Dialog, DialogContent } from "@/components/ui/dialog";

function Command({ className, ...props }: React.ComponentProps<typeof CommandPrimitive>) {
 return (
 <CommandPrimitive
 data-slot="command"
 className={cn(
 "bg-popover text-popover-foreground flex h-full w-full flex-col overflow-hidden rounded-md",
 className,
 )}
 {...props}
 />
 );
}

type CommandDialogProps = DialogPrimitive.DialogProps & {
 contentClassName?: string;
};

function CommandDialog({ children, contentClassName, ...props }: CommandDialogProps) {
 return (
 <Dialog {...props}>
 <DialogContent className={cn("overflow-hidden p-0 shadow-lg", contentClassName)}>
 <DialogPrimitive.Title className="sr-only">Command palette</DialogPrimitive.Title>
 <DialogPrimitive.Description className="sr-only">
 Search for pages and actions.
 </DialogPrimitive.Description>
 <Command className="[&_[cmdk-group-heading]]:text-muted-foreground [&_[cmdk-group-heading]]:px-2 [&_[cmdk-group-heading]]:py-1.5 [&_[cmdk-group-heading]]:text-xs [&_[cmdk-group-heading]]:font-medium">
 {children}
 </Command>
 </DialogContent>
 </Dialog>
 );
}

function CommandInput({
 className,
 ...props
}: React.ComponentProps<typeof CommandPrimitive.Input>) {
 return (
 <div data-slot="command-input-wrapper" className="flex items-center border-b px-3">
 <Search className="mr-2 h-4 w-4 shrink-0 opacity-60" aria-hidden="true" />
 <CommandPrimitive.Input
 data-slot="command-input"
 className={cn(
 "placeholder:text-muted-foreground flex h-11 w-full rounded-md bg-transparent py-3 text-sm outline-none disabled:cursor-not-allowed disabled:opacity-50",
 className,
 )}
 {...props}
 />
 </div>
 );
}

function CommandList({ className, ...props }: React.ComponentProps<typeof CommandPrimitive.List>) {
 return (
 <CommandPrimitive.List
 data-slot="command-list"
 className={cn("max-h-[340px] overflow-x-hidden overflow-y-auto", className)}
 {...props}
 />
 );
}

function CommandEmpty(props: React.ComponentProps<typeof CommandPrimitive.Empty>) {
 return (
 <CommandPrimitive.Empty
 data-slot="command-empty"
 className="text-muted-foreground py-6 text-center text-sm"
 {...props}
 />
 );
}

function CommandGroup({
 className,
 ...props
}: React.ComponentProps<typeof CommandPrimitive.Group>) {
 return (
 <CommandPrimitive.Group
 data-slot="command-group"
 className={cn("text-foreground overflow-hidden p-1", className)}
 {...props}
 />
 );
}

function CommandSeparator({
 className,
 ...props
}: React.ComponentProps<typeof CommandPrimitive.Separator>) {
 return (
 <CommandPrimitive.Separator
 data-slot="command-separator"
 className={cn("bg-border -mx-1 h-px", className)}
 {...props}
 />
 );
}

function CommandItem({ className, ...props }: React.ComponentProps<typeof CommandPrimitive.Item>) {
 return (
 <CommandPrimitive.Item
 data-slot="command-item"
 className={cn(
 "data-[disabled=true]:text-muted-foreground data-[selected=true]:bg-accent data-[selected=true]:text-accent-foreground relative flex cursor-default items-center gap-2 rounded-sm px-2 py-2 text-sm outline-none select-none data-[disabled=true]:pointer-events-none",
 className,
 )}
 {...props}
 />
 );
}

function CommandShortcut({ className, ...props }: React.ComponentProps<"span">) {
 return (
 <span
 data-slot="command-shortcut"
 className={cn("text-muted-foreground ml-auto text-xs tracking-widest", className)}
 {...props}
 />
 );
}

export {
 Command,
 CommandDialog,
 CommandEmpty,
 CommandGroup,
 CommandInput,
 CommandItem,
 CommandList,
 CommandSeparator,
 CommandShortcut,
};
