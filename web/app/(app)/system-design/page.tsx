import { SystemDesignStartClient } from "@/app/(app)/system-design/_components/system-design-start-client";
import { Page } from "@/components/layout/page";

type SystemDesignPageProps = {
 searchParams?: Promise<{
 title?: string | string[];
 problemStatement?: string | string[];
 templateId?: string | string[];
 }>;
};

function first(value: string | string[] | undefined): string | undefined {
 if (!value) return undefined;
 return Array.isArray(value) ? value[0] : value;
}

export default async function SystemDesignPage({ searchParams }: SystemDesignPageProps) {
 const params = await searchParams;

 const initialTitle = first(params?.title) ?? "";
 const initialProblemStatement = first(params?.problemStatement) ?? "";
 const initialTemplateId = first(params?.templateId) ?? "";

 return (
 <Page>
 <SystemDesignStartClient
 initialTitle={initialTitle}
 initialProblemStatement={initialProblemStatement}
 initialTemplateId={initialTemplateId}
 />
 </Page>
 );
}
