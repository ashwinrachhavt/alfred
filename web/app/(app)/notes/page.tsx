import { NotesWorkbenchClient } from "@/app/(app)/notes/_components/notes-workbench-client";

type NotesPageProps = {
  searchParams?: Promise<{
    note?: string | string[];
  }>;
};

function first(value: string | string[] | undefined): string | undefined {
  if (!value) return undefined;
  return Array.isArray(value) ? value[0] : value;
}

export default async function NotesPage({ searchParams }: NotesPageProps) {
  const params = await searchParams;
  const initialNoteId = first(params?.note) ?? null;

  return (
    <div className="h-[calc(100dvh-3.5rem)] w-full">
      <NotesWorkbenchClient initialNoteId={initialNoteId} />
    </div>
  );
}

