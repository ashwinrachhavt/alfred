import { describe, expect, it } from "vitest";

import {
  AI_COMMANDS,
  aiCommandsByGroup,
  editSubmenu,
  fillPromptTemplate,
  getAICommand,
  slashAICommands,
} from "../commands";

describe("AI command registry", () => {
  it("ids are unique", () => {
    const ids = AI_COMMANDS.map((c) => c.id);
    expect(new Set(ids).size).toBe(ids.length);
  });

  it("every group is non-empty", () => {
    const groups = aiCommandsByGroup();
    expect(groups.edit.length).toBeGreaterThan(0);
    expect(groups.generate.length).toBeGreaterThan(0);
    expect(groups.draft.length).toBeGreaterThan(0);
    expect(groups.ask.length).toBeGreaterThan(0);
  });

  it("aiCommandsByGroup partitions every command into exactly one group", () => {
    const groups = aiCommandsByGroup();
    const total =
      groups.edit.length + groups.generate.length + groups.draft.length + groups.ask.length;
    expect(total).toBe(AI_COMMANDS.length);
  });

  it("every command has a non-empty label", () => {
    for (const command of AI_COMMANDS) {
      expect(command.label.trim().length).toBeGreaterThan(0);
    }
  });

  it("every non-panel command has a non-empty promptTemplate", () => {
    const inline = AI_COMMANDS.filter((c) => !c.panel);
    for (const command of inline) {
      expect(command.promptTemplate.trim().length).toBeGreaterThan(0);
    }
  });

  it("ask group commands are panel-mode", () => {
    const groups = aiCommandsByGroup();
    for (const command of groups.ask) {
      expect(command.panel).toBe(true);
    }
  });

  it("slashAICommands returns only commands with a slashAlias", () => {
    const slash = slashAICommands();
    expect(slash.length).toBeGreaterThan(0);
    for (const command of slash) {
      expect(command.slashAlias).toBeTruthy();
    }
  });

  it("slashAlias values are unique", () => {
    const aliases = slashAICommands().map((c) => c.slashAlias);
    expect(new Set(aliases).size).toBe(aliases.length);
  });

  it("editSubmenu returns base, tone, and translate sets", () => {
    const submenu = editSubmenu();
    expect(submenu.base.length).toBeGreaterThan(0);
    expect(submenu.tone.length).toBeGreaterThan(0);
    expect(submenu.translate.length).toBeGreaterThan(0);
    for (const command of submenu.tone) {
      expect(command.id.startsWith("change_tone:")).toBe(true);
    }
    for (const command of submenu.translate) {
      expect(command.id.startsWith("translate:")).toBe(true);
    }
  });

  it("getAICommand looks up by id", () => {
    const improve = getAICommand("improve_writing");
    expect(improve?.label).toBe("Improve writing");
    expect(getAICommand("nonsense")).toBeUndefined();
  });

  it("fillPromptTemplate substitutes placeholders", () => {
    const filled = fillPromptTemplate("Rewrite {selection} in {paragraph} style", {
      selection: "this text",
      paragraph: "casual",
    });
    expect(filled).toBe("Rewrite this text in casual style");
  });

  it("fillPromptTemplate handles missing values without leaving placeholders", () => {
    const filled = fillPromptTemplate("Rewrite {selection}", {});
    expect(filled).toBe("Rewrite ");
  });
});
