import { describe, expect, it } from "vitest";

import { buildNexusGraph } from "../graph-adapter";
import type { NexusGraph } from "../types";

describe("buildNexusGraph", () => {
  it("keeps domain edge type out of Sigma's reserved renderer type attribute", () => {
    const data: NexusGraph = {
      nodes: [
        {
          card_id: 1,
          title: "Source",
          topic: null,
          tags: [],
          bloom_level: 1,
          cluster_id: null,
        },
        {
          card_id: 2,
          title: "Target",
          topic: null,
          tags: [],
          bloom_level: 1,
          cluster_id: null,
        },
      ],
      edges: [{ source: 1, target: 2, type: "ai-suggested" }],
    };

    const graph = buildNexusGraph(data);
    const [edge] = graph.edges();
    const attrs = graph.getEdgeAttributes(edge);

    expect(attrs.relationType).toBe("ai-suggested");
    expect(attrs).not.toHaveProperty("type");
  });
});
