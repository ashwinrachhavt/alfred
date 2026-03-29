import { redirect } from "next/navigation";

import { auth } from "@clerk/nextjs/server";

import HeroSection from "@/components/hero-sections-05";
import { isClerkEnabled } from "@/lib/auth";

export default async function Home() {
 if (isClerkEnabled()) {
 try {
 const { userId } = await auth();
 if (userId) {
 redirect("/inbox");
 }
 } catch {
 // Clerk middleware may not have run — fall through to landing.
 }
 }

 return <HeroSection />;
}
