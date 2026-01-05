"use client"

import Link from "next/link"

import { AppNavigationMenu } from "@/components/app-navigation-menu"
import { AppSidebar } from "@/components/app-sidebar"
import { ThemeToggle } from "@/components/theme-toggle"
import { SidebarInset, SidebarProvider, SidebarTrigger } from "@/components/ui/sidebar"

export function AppShell({
  children,
  defaultSidebarOpen,
}: {
  children: React.ReactNode
  defaultSidebarOpen: boolean
}) {
  return (
    <SidebarProvider defaultOpen={defaultSidebarOpen}>
      <AppSidebar />
      <SidebarInset>
        <header className="sticky top-0 z-40 border-b bg-background/90 backdrop-blur supports-[backdrop-filter]:bg-background/60">
          <div className="mx-auto flex w-full max-w-6xl items-center justify-between gap-3 px-4 py-3">
            <div className="flex items-center gap-3">
              <SidebarTrigger />
              <Link href="/" className="font-semibold tracking-tight">
                Alfred
              </Link>
              <span className="hidden text-xs text-muted-foreground sm:inline">
                Knowledge workbench
              </span>
            </div>
            <div className="flex items-center gap-2">
              <nav className="hidden items-center md:flex">
                <AppNavigationMenu />
              </nav>
              <ThemeToggle />
            </div>
          </div>
        </header>
        <main>{children}</main>
      </SidebarInset>
    </SidebarProvider>
  )
}
