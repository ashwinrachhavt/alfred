import { InboxStream } from "./_components/inbox-stream";

export const metadata = { title: "Inbox — Alfred" };

export default function InboxPage() {
  return (
    <div className="mx-auto max-w-5xl px-8 py-8">
      <InboxStream />
    </div>
  );
}
