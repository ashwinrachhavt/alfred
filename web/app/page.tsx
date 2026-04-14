import { redirect } from "next/navigation";

import HeroSection from "@/components/hero-sections-05";
import { isClerkEnabled } from "@/lib/auth";
import { getAuth } from "@/lib/auth.server";

export default async function Home() {
 if (isClerkEnabled()) {
 try {
 const { userId } = await getAuth();
 if (userId) {
 redirect("/inbox");
 }
 } catch {
 // Clerk middleware may not have run or keys are invalid — fall through.
 }
 } else {
 // No auth configured — go straight to the app.
 redirect("/inbox");
 }

 return <HeroSection />;
}
