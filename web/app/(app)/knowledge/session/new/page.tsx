"use client";

/**
 * /knowledge/session/new — creates a sitting and redirects to it.
 *
 * Client component because it uses hooks (useCreateSession / useRouter).
 * Respects the NEXT_PUBLIC_ZETTEL_WORKSPACE_V2 feature flag.
 */

import { useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import { Loader2Icon } from "lucide-react";

import { useCreateSession } from "@/features/workspace/mutations";

export default function NewSessionPage() {
  const router = useRouter();
  const createSession = useCreateSession();
  const triggered = useRef(false);

  useEffect(() => {
    if (triggered.current) return;
    triggered.current = true;

    if (process.env.NEXT_PUBLIC_ZETTEL_WORKSPACE_V2 === "false") {
      router.replace("/knowledge");
      return;
    }

    (async () => {
      try {
        const result = await createSession.mutateAsync({});
        router.replace(`/knowledge/session/${result.id}`);
      } catch {
        // Creation failed — bounce back to knowledge hub rather than showing a blank page.
        router.replace("/knowledge");
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div className="flex min-h-[60vh] items-center justify-center">
      <div className="flex flex-col items-center gap-3 font-mono text-[10px] uppercase tracking-wider text-[var(--alfred-text-tertiary)]">
        <Loader2Icon className="size-4 animate-spin text-foreground" />
        <span>Opening a new sitting...</span>
      </div>
    </div>
  );
}
