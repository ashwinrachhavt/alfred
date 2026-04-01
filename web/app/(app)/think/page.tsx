import { Page } from "@/components/layout/page";
import { ThinkClient } from "@/app/(app)/think/_components/think-client";

export default function ThinkPage() {
 return (
 <Page size="full" className="p-0">
 <ThinkClient />
 </Page>
 );
}
