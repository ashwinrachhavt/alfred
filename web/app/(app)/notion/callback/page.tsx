"use client";

import { Suspense, useEffect, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Loader2, CheckCircle2, XCircle } from "lucide-react";

import { apiPostJson } from "@/lib/api/client";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

type ExchangeResponse = {
 ok: boolean;
 workspace?: { workspace_id: string; workspace_name?: string } | null;
 error?: string | null;
};

function NotionCallbackContent() {
 const params = useSearchParams();
 const router = useRouter();
 const exchanged = useRef(false);

 const [status, setStatus] = useState<"loading" | "success" | "error">("loading");
 const [message, setMessage] = useState("Connecting to Notion...");

 useEffect(() => {
 if (exchanged.current) return;
 exchanged.current = true;

 const code = params.get("code");
 const state = params.get("state");
 const error = params.get("error");

 if (error) {
 setStatus("error");
 setMessage(`Notion authorization was denied: ${error}`);
 return;
 }

 if (!code || !state) {
 setStatus("error");
 setMessage("Missing authorization code or state from Notion.");
 return;
 }

 apiPostJson<ExchangeResponse, { code: string; state: string }>(
 "/api/notion/oauth/exchange",
 { code, state },
 )
 .then((resp) => {
 if (resp.ok) {
 setStatus("success");
 const name = resp.workspace?.workspace_name ?? "your workspace";
 setMessage(`Connected to ${name}!`);
 } else {
 setStatus("error");
 setMessage(resp.error ?? "Token exchange failed.");
 }
 })
 .catch((err) => {
 setStatus("error");
 setMessage(err instanceof Error ? err.message : "Token exchange failed.");
 });
 }, [params]);

 return (
 <div className="flex min-h-[60vh] items-center justify-center">
 <Card className="w-full max-w-md">
 <CardContent className="flex flex-col items-center gap-4 pt-8 pb-6 text-center">
 {status === "loading" && (
 <Loader2 className="text-muted-foreground h-10 w-10 animate-spin" />
 )}
 {status === "success" && (
 <CheckCircle2 className="h-10 w-10 text-green-500" />
 )}
 {status === "error" && (
 <XCircle className="h-10 w-10 text-red-500" />
 )}

 <p className="text-lg font-medium">{message}</p>

 {status !== "loading" && (
 <Button
 variant={status === "success" ? "default" : "outline"}
 onClick={() => router.push("/notion")}
 >
 {status === "success" ? "Go to Notion" : "Back to Notion"}
 </Button>
 )}
 </CardContent>
 </Card>
 </div>
 );
}

export default function NotionCallbackPage() {
 return (
 <Suspense
 fallback={
 <div className="flex min-h-[60vh] items-center justify-center">
 <Loader2 className="text-muted-foreground h-10 w-10 animate-spin" />
 </div>
 }
 >
 <NotionCallbackContent />
 </Suspense>
 );
}
