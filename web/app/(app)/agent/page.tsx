import { redirect } from "next/navigation";

export const metadata = { title: "Alfred Agent" };

/**
 * The standalone /agent page is deprecated.
 * Agent chat now lives in the global AI panel (Cmd+J).
 * Redirect to /notes — the AI panel will open via client-side hydration.
 */
export default function AgentPage() {
 redirect("/notes");
}
