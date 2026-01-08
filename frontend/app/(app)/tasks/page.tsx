import { Page } from "@/components/layout/page";
import { TasksClient } from "@/app/(app)/tasks/_components/tasks-client";

type TasksPageProps = {
  searchParams?: Promise<{
    taskId?: string | string[];
  }>;
};

export default async function TasksPage({ searchParams }: TasksPageProps) {
  const resolvedSearchParams = await searchParams;
  const taskIdValue = resolvedSearchParams?.taskId;
  const taskId = Array.isArray(taskIdValue) ? taskIdValue[0] : taskIdValue;
  return (
    <Page>
      <TasksClient initialTaskId={taskId} />
    </Page>
  );
}
