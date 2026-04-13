import type { Metadata } from "next";
import { Source_Serif_4, DM_Sans, JetBrains_Mono } from "next/font/google";
import { ClerkProvider } from "@clerk/nextjs";
import "./globals.css";
import "@excalidraw/excalidraw/index.css";

import { Providers } from "@/app/providers";

const sourceSerif = Source_Serif_4({
 variable: "--font-source-serif",
 subsets: ["latin"],
});

const dmSans = DM_Sans({
 variable: "--font-dm-sans",
 subsets: ["latin"],
});

const jetbrainsMono = JetBrains_Mono({
 variable: "--font-jetbrains-mono",
 subsets: ["latin"],
});

export const metadata: Metadata = {
 title: "Alfred",
 description: "Your knowledge factory — ingest, decompose, connect, think.",
};

export default function RootLayout({
 children,
}: Readonly<{
 children: React.ReactNode;
}>) {
 return (
 <html lang="en" suppressHydrationWarning>
 <head>
 {/* Prevent accent theme flash — read localStorage before first paint.
 This is a static inline script with no user input, identical to the
 pattern used by next-themes for dark mode FOUC prevention. */}
 <script
 dangerouslySetInnerHTML={{
 __html:`(function(){try{var a=localStorage.getItem("alfred-accent-theme");if(a&&a!=="terracotta")document.documentElement.setAttribute("data-accent",a)}catch(e){}})()`,
 }}
 />
 </head>
 <body
 className={`${sourceSerif.variable} ${dmSans.variable} ${jetbrainsMono.variable} font-sans antialiased`}
 >
 <ClerkProvider>
 <Providers>{children}</Providers>
 </ClerkProvider>
 </body>
 </html>
 );
}
