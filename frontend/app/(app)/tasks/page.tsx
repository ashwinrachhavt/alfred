import { Page } from "@/components/layout/page";
import { TasksClient } from "@/app/(app)/tasks/_components/tasks-client";

type TasksPageProps = {
  searchParams?: {
    taskId?: string | string[];
  };
};

export default function TasksPage({ searchParams }: TasksPageProps) {
  const taskId = Array.isArray(searchParams?.taskId)
    ? searchParams?.taskId[0]
    : searchParams?.taskId;
  return (
    <Page>
      <TasksClient initialTaskId={taskId} />
    </Page>
  );
}
