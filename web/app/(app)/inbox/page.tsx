import { InboxStream } from "./_components/inbox-stream";

export const metadata = { title: "Inbox — Alfred" };

export default function InboxPage() {
  return (
    <div className="mx-auto max-w-4xl px-4 py-6">
      <InboxStream />
    </div>
  );
}
