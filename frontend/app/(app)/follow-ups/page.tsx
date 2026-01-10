import { Page } from "@/components/layout/page";
import { FollowUpsClient } from "@/app/(app)/follow-ups/_components/follow-ups-client";

type FollowUpsPageProps = {
  searchParams?: Promise<{
    title?: string | string[];
    dueAt?: string | string[];
    dueInMinutes?: string | string[];
    href?: string | string[];
    focus?: string | string[];
  }>;
};

function first(value: string | string[] | undefined): string | undefined {
  if (!value) return undefined;
  return Array.isArray(value) ? value[0] : value;
}

export default async function FollowUpsPage({ searchParams }: FollowUpsPageProps) {
  const resolved = await searchParams;

  return (
    <Page size="wide">
      <FollowUpsClient
        initialTitle={first(resolved?.title) ?? ""}
        initialDueAt={first(resolved?.dueAt) ?? ""}
        initialDueInMinutes={first(resolved?.dueInMinutes) ?? ""}
        initialHref={first(resolved?.href) ?? ""}
        focusId={first(resolved?.focus) ?? ""}
      />
    </Page>
  );
}
