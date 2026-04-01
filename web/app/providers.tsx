"use client";

import { useState } from "react";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import { AppCommandPaletteProvider } from "@/components/app-command-palette";
import { ThemeProvider } from "@/components/theme-provider";
import { Toaster } from "@/components/ui/sonner";
import { TaskTrackerProvider } from "@/features/tasks/task-tracker-provider";

function createQueryClient(): QueryClient {
 return new QueryClient({
 defaultOptions: {
 queries: {
 retry: 1,
 refetchOnWindowFocus: false,
 staleTime: 30_000,
 },
 },
 });
}

export function Providers({ children }: { children: React.ReactNode }) {
 const [queryClient] = useState(() => createQueryClient());

 return (
 <ThemeProvider
 attribute="class"
 defaultTheme="dark"
 enableSystem={false}
 enableColorScheme
 disableTransitionOnChange
 >
 <QueryClientProvider client={queryClient}>
 <TaskTrackerProvider>
 <AppCommandPaletteProvider>
 <a
 href="#main-content"
 className="focus:bg-background focus:text-foreground focus:ring-ring sr-only fixed top-4 left-4 z-50 rounded-md px-3 py-2 text-sm shadow-sm focus:not-sr-only focus:ring-2 focus:outline-none"
 >
 Skip to content
 </a>
 {children}
 <Toaster />
 </AppCommandPaletteProvider>
 </TaskTrackerProvider>
 </QueryClientProvider>
 </ThemeProvider>
 );
}
