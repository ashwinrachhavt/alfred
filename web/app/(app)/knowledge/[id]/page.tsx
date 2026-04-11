import { ZettelFullPageClient } from "./_components/zettel-full-page-client";

type ZettelPageProps = {
  params: Promise<{ id: string }>;
};

export default async function ZettelPage({ params }: ZettelPageProps) {
  const { id } = await params;
  return <ZettelFullPageClient zettelId={Number(id)} />;
}
