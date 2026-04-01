import { Page } from "@/components/layout/page";

import { DocumentReaderClient } from "./_components/document-reader-client";

type DocumentReaderPageProps = {
 params: { id: string } | Promise<{ id: string }>;
};

export default async function DocumentReaderPage({ params }: DocumentReaderPageProps) {
 const resolvedParams = await Promise.resolve(params);

 return (
 <Page size="comfortable">
 <DocumentReaderClient docId={resolvedParams.id} />
 </Page>
 );
}
