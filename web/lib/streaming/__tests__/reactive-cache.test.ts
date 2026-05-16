import { QueryClient } from "@tanstack/react-query";
import { afterEach, describe, expect, it, vi } from "vitest";

import {
  bindStreamingQueryClient,
  notifyStreamCacheEvent,
} from "../reactive-cache";

afterEach(() => {
  bindStreamingQueryClient(null);
});

describe("notifyStreamCacheEvent", () => {
  it("invalidates zettel query families when a zettel artifact is created", () => {
    const queryClient = new QueryClient();
    const invalidate = vi
      .spyOn(queryClient, "invalidateQueries")
      .mockResolvedValue(undefined);
    bindStreamingQueryClient(queryClient);

    notifyStreamCacheEvent("artifact", {
      type: "zettel",
      action: "created",
      id: 42,
      title: "New card",
    });

    expect(invalidate).toHaveBeenCalledWith({ queryKey: ["zettels"] });
    expect(invalidate).toHaveBeenCalledWith({ queryKey: ["zettel-topics"] });
    expect(invalidate).toHaveBeenCalledWith({ queryKey: ["zettel-tags"] });
  });

  it("invalidates zettel query families for streamed zettel creation events", () => {
    const queryClient = new QueryClient();
    const invalidate = vi
      .spyOn(queryClient, "invalidateQueries")
      .mockResolvedValue(undefined);
    bindStreamingQueryClient(queryClient);

    notifyStreamCacheEvent("card_saved", { id: 7, title: "Saved" });

    expect(invalidate).toHaveBeenCalledWith({ queryKey: ["zettels"] });
    expect(invalidate).toHaveBeenCalledWith({ queryKey: ["zettel-topics"] });
    expect(invalidate).toHaveBeenCalledWith({ queryKey: ["zettel-tags"] });
  });

  it("invalidates research report queries when a report is completed", () => {
    const queryClient = new QueryClient();
    const invalidate = vi
      .spyOn(queryClient, "invalidateQueries")
      .mockResolvedValue(undefined);
    bindStreamingQueryClient(queryClient);

    notifyStreamCacheEvent("done", { report_id: "report-1" });

    expect(invalidate).toHaveBeenCalledWith({ queryKey: ["research", "reports"] });
    expect(invalidate).toHaveBeenCalledWith({
      queryKey: ["research", "reports", "by-id", "report-1"],
    });
  });
});
