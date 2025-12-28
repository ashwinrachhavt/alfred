import Link from "next/link";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export default function NotFound() {
  return (
    <div className="mx-auto w-full max-w-3xl px-4 py-14">
      <Card>
        <CardHeader>
          <CardTitle>Page not found</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <p className="text-sm text-muted-foreground">
            The page you’re looking for doesn’t exist (or moved).
          </p>
          <div className="flex flex-wrap gap-2">
            <Button asChild>
              <Link href="/">Home</Link>
            </Button>
            <Button asChild variant="outline">
              <Link href="/system-design">System Design</Link>
            </Button>
            <Button asChild variant="outline">
              <Link href="/interview-prep">Interview Prep</Link>
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

