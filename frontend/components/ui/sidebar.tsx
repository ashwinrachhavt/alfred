"use client";

import * as React from "react";

import { Slot } from "@radix-ui/react-slot";
import { PanelLeft } from "lucide-react";

import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";

type SidebarState = "expanded" | "collapsed";

const SIDEBAR_COOKIE_NAME = "sidebar_state";
const SIDEBAR_COOKIE_MAX_AGE = 60 * 60 * 24 * 365;
const SIDEBAR_KEYBOARD_SHORTCUT = "b";

const SIDEBAR_WIDTH = "16rem";
const SIDEBAR_WIDTH_ICON = "3.5rem";

type SidebarContextValue = {
  state: SidebarState;
  open: boolean;
  setOpen: (value: boolean | ((open: boolean) => boolean)) => void;
  openMobile: boolean;
  setOpenMobile: (open: boolean) => void;
  isMobile: boolean;
  toggleSidebar: () => void;
};

const SidebarContext = React.createContext<SidebarContextValue | null>(null);

function useIsMobile(breakpointPx = 768) {
  const [isMobile, setIsMobile] = React.useState(false);

  React.useEffect(() => {
    const media = window.matchMedia(`(max-width: ${breakpointPx}px)`);
    const onChange = () => setIsMobile(media.matches);
    onChange();
    media.addEventListener("change", onChange);
    return () => media.removeEventListener("change", onChange);
  }, [breakpointPx]);

  return isMobile;
}

type SidebarProviderProps = React.PropsWithChildren<{
  defaultOpen?: boolean;
  open?: boolean;
  onOpenChange?: (open: boolean) => void;
  style?: React.CSSProperties & {
    ["--sidebar-width"]?: string;
    ["--sidebar-width-icon"]?: string;
  };
}>;

export function SidebarProvider({
  children,
  defaultOpen = true,
  open: openProp,
  onOpenChange: setOpenProp,
  style,
}: SidebarProviderProps) {
  const isMobile = useIsMobile();

  const [_open, _setOpen] = React.useState(defaultOpen);
  const [openMobile, setOpenMobile] = React.useState(false);

  const open = openProp ?? _open;
  const state: SidebarState = open ? "expanded" : "collapsed";

  const setOpen = React.useCallback(
    (value: boolean | ((open: boolean) => boolean)) => {
      const nextOpen = typeof value === "function" ? value(open) : value;

      if (setOpenProp) setOpenProp(nextOpen);
      else _setOpen(nextOpen);

      document.cookie = `${SIDEBAR_COOKIE_NAME}=${nextOpen}; path=/; max-age=${SIDEBAR_COOKIE_MAX_AGE}`;
    },
    [open, setOpenProp],
  );

  const toggleSidebar = React.useCallback(() => {
    if (isMobile) {
      setOpenMobile(!openMobile);
      return;
    }
    setOpen((prev) => !prev);
  }, [isMobile, openMobile, setOpen]);

  React.useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      if (!(event.ctrlKey || event.metaKey)) return;
      if (event.key.toLowerCase() !== SIDEBAR_KEYBOARD_SHORTCUT) return;
      event.preventDefault();
      toggleSidebar();
    }

    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [toggleSidebar]);

  const value = React.useMemo<SidebarContextValue>(
    () => ({
      state,
      open,
      setOpen,
      openMobile,
      setOpenMobile,
      isMobile,
      toggleSidebar,
    }),
    [isMobile, open, openMobile, setOpen, state, toggleSidebar],
  );

  return (
    <SidebarContext.Provider value={value}>
      <div
        style={{
          ["--sidebar-width" as never]: SIDEBAR_WIDTH,
          ["--sidebar-width-icon" as never]: SIDEBAR_WIDTH_ICON,
          ...style,
        }}
        className="min-h-dvh"
      >
        {children}
      </div>
    </SidebarContext.Provider>
  );
}

export function useSidebar() {
  const ctx = React.useContext(SidebarContext);
  if (!ctx) throw new Error("useSidebar must be used within a SidebarProvider.");
  return ctx;
}

type SidebarProps = React.ComponentPropsWithoutRef<"aside"> & {
  side?: "left" | "right";
  variant?: "sidebar" | "floating" | "inset";
  collapsible?: "offcanvas" | "icon" | "none";
};

export function Sidebar({
  className,
  side = "left",
  variant = "sidebar",
  collapsible = "icon",
  ...props
}: SidebarProps) {
  const { isMobile, open, openMobile, setOpenMobile } = useSidebar();

  const desktopWidth = open ? "var(--sidebar-width)" : "var(--sidebar-width-icon)";
  const shouldOverlay = isMobile;
  const mobileOpen = openMobile;

  return (
    <>
      {shouldOverlay ? (
        <div
          data-slot="sidebar-overlay"
          className={cn(
            "bg-background/60 fixed inset-0 z-40 backdrop-blur-sm transition-opacity",
            mobileOpen ? "opacity-100" : "pointer-events-none opacity-0",
          )}
          onClick={() => setOpenMobile(false)}
          aria-hidden="true"
        />
      ) : null}

      <aside
        data-slot="sidebar"
        data-side={side}
        data-variant={variant}
        data-collapsible={collapsible}
        data-state={open ? "expanded" : "collapsed"}
        className={cn(
          "group bg-sidebar text-sidebar-foreground z-50 flex h-dvh flex-col border-r",
          "supports-[backdrop-filter]:bg-sidebar/90 supports-[backdrop-filter]:backdrop-blur",
          shouldOverlay
            ? cn(
                "fixed inset-y-0 left-0 w-[var(--sidebar-width)] -translate-x-full transition-transform duration-200",
                mobileOpen && "translate-x-0",
              )
            : "sticky top-0",
          className,
        )}
        style={!shouldOverlay ? { width: desktopWidth } : undefined}
        {...props}
      />
    </>
  );
}

export function SidebarInset({ className, ...props }: React.ComponentPropsWithoutRef<"div">) {
  const { open, isMobile } = useSidebar();
  return (
    <div
      data-slot="sidebar-inset"
      className={cn("min-h-dvh", className)}
      style={{
        paddingLeft: isMobile
          ? undefined
          : open
            ? "var(--sidebar-width)"
            : "var(--sidebar-width-icon)",
      }}
      {...props}
    />
  );
}

export function SidebarHeader({ className, ...props }: React.ComponentPropsWithoutRef<"div">) {
  return (
    <div
      data-slot="sidebar-header"
      className={cn("bg-sidebar/80 sticky top-0 z-10 border-b p-3 backdrop-blur", className)}
      {...props}
    />
  );
}

export function SidebarFooter({ className, ...props }: React.ComponentPropsWithoutRef<"div">) {
  return (
    <div
      data-slot="sidebar-footer"
      className={cn("bg-sidebar/80 sticky bottom-0 z-10 border-t p-3 backdrop-blur", className)}
      {...props}
    />
  );
}

export function SidebarContent({ className, ...props }: React.ComponentPropsWithoutRef<"div">) {
  return (
    <div
      data-slot="sidebar-content"
      className={cn("flex-1 overflow-y-auto p-2", className)}
      {...props}
    />
  );
}

export function SidebarGroup({ className, ...props }: React.ComponentPropsWithoutRef<"div">) {
  return <div data-slot="sidebar-group" className={cn("space-y-2 p-1", className)} {...props} />;
}

export function SidebarGroupLabel({ className, ...props }: React.ComponentPropsWithoutRef<"div">) {
  return (
    <div
      data-slot="sidebar-group-label"
      className={cn(
        "text-sidebar-foreground/70 px-2 text-xs font-medium",
        "group-data-[state=collapsed]:sr-only",
        className,
      )}
      {...props}
    />
  );
}

export function SidebarGroupContent({
  className,
  ...props
}: React.ComponentPropsWithoutRef<"div">) {
  return (
    <div data-slot="sidebar-group-content" className={cn("space-y-1", className)} {...props} />
  );
}

export function SidebarMenu({ className, ...props }: React.ComponentPropsWithoutRef<"ul">) {
  return <ul data-slot="sidebar-menu" className={cn("space-y-1", className)} {...props} />;
}

export function SidebarMenuItem({ className, ...props }: React.ComponentPropsWithoutRef<"li">) {
  return <li data-slot="sidebar-menu-item" className={cn("relative", className)} {...props} />;
}

type SidebarMenuButtonProps = React.ComponentPropsWithoutRef<"button"> & {
  asChild?: boolean;
  isActive?: boolean;
};

export function SidebarMenuButton({
  className,
  asChild,
  isActive,
  ...props
}: SidebarMenuButtonProps) {
  const Comp = asChild ? Slot : "button";

  return (
    <Comp
      data-slot="sidebar-menu-button"
      data-active={isActive ? "true" : "false"}
      className={cn(
        "group/menu-button flex w-full items-center gap-2 rounded-md px-2 py-2 text-sm transition-colors",
        "hover:bg-sidebar-accent hover:text-sidebar-accent-foreground",
        "focus-visible:ring-sidebar-ring focus-visible:ring-2 focus-visible:outline-none",
        isActive && "bg-sidebar-accent text-sidebar-accent-foreground",
        className,
      )}
      {...props}
    />
  );
}

export function SidebarTrigger({ className }: { className?: string }) {
  const { toggleSidebar } = useSidebar();
  return (
    <Button
      type="button"
      variant="ghost"
      size="icon"
      className={cn("h-9 w-9", className)}
      onClick={toggleSidebar}
      aria-label="Toggle sidebar"
    >
      <PanelLeft className="h-4 w-4" />
    </Button>
  );
}
