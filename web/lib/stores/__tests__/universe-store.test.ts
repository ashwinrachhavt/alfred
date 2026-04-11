import { describe, it, expect, beforeEach } from "vitest";
import { useUniverseStore } from "../universe-store";

beforeEach(() => {
  useUniverseStore.setState({
    selectedNodeIds: [],
    hoveredNodeId: null,
    cameraTarget: null,
    searchQuery: "",
    audioEnabled: false,
    isTimeLapsePlaying: false,
  });
});

describe("universe-store", () => {
  it("selects a node", () => {
    useUniverseStore.getState().selectNode(1);
    expect(useUniverseStore.getState().selectedNodeIds).toEqual([1]);
  });

  it("does not duplicate node selection", () => {
    useUniverseStore.getState().selectNode(1);
    useUniverseStore.getState().selectNode(1);
    expect(useUniverseStore.getState().selectedNodeIds).toEqual([1]);
  });

  it("caps selection at 5 nodes", () => {
    const s = useUniverseStore.getState();
    [1, 2, 3, 4, 5, 6].forEach((id) => s.selectNode(id));
    expect(useUniverseStore.getState().selectedNodeIds).toHaveLength(5);
    expect(useUniverseStore.getState().selectedNodeIds).not.toContain(6);
  });

  it("deselects a node", () => {
    const s = useUniverseStore.getState();
    s.selectNode(1);
    s.selectNode(2);
    s.deselectNode(1);
    expect(useUniverseStore.getState().selectedNodeIds).toEqual([2]);
  });

  it("clears selection", () => {
    const s = useUniverseStore.getState();
    s.selectNode(1);
    s.selectNode(2);
    s.clearSelection();
    expect(useUniverseStore.getState().selectedNodeIds).toEqual([]);
  });

  it("toggles audio", () => {
    useUniverseStore.getState().toggleAudio();
    expect(useUniverseStore.getState().audioEnabled).toBe(true);
    useUniverseStore.getState().toggleAudio();
    expect(useUniverseStore.getState().audioEnabled).toBe(false);
  });

  it("sets search query", () => {
    useUniverseStore.getState().setSearchQuery("philosophy");
    expect(useUniverseStore.getState().searchQuery).toBe("philosophy");
  });
});
