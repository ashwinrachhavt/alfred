import { mergeAttributes, Node } from "@tiptap/core";

export interface WikiLinkOptions {
  /**
   * Called when a wiki-link is clicked. Receives the card ID.
   */
  onClickLink?: (cardId: string) => void;
}

declare module "@tiptap/core" {
  interface Commands<ReturnType> {
    wikiLink: {
      /**
       * Insert a wiki-link node at the current cursor position.
       */
      insertWikiLink: (attrs: { cardId: string; title: string }) => ReturnType;
    };
  }
}

/**
 * TipTap extension for [[wiki-links]] to zettel cards.
 *
 * Storage format:
 * - TipTap JSON: { type: "wikiLink", attrs: { cardId, title } }
 * - Markdown: [[title|cardId]]
 * - HTML: <span data-wiki-link data-card-id="...">title</span>
 */
export const WikiLink = Node.create<WikiLinkOptions>({
  name: "wikiLink",
  group: "inline",
  inline: true,
  atom: true,

  addOptions() {
    return {
      onClickLink: undefined,
    };
  },

  addAttributes() {
    return {
      cardId: {
        default: null,
        parseHTML: (element) => element.getAttribute("data-card-id"),
        renderHTML: (attributes) => ({
          "data-card-id": attributes.cardId as string,
        }),
      },
      title: {
        default: "",
        parseHTML: (element) => element.textContent ?? "",
        renderHTML: () => ({}),
      },
    };
  },

  parseHTML() {
    return [{ tag: "span[data-wiki-link]" }];
  },

  renderHTML({ node, HTMLAttributes }) {
    return [
      "span",
      mergeAttributes(HTMLAttributes, {
        "data-wiki-link": "",
        class: "wiki-link",
      }),
      node.attrs.title as string,
    ];
  },

  addCommands() {
    return {
      insertWikiLink:
        (attrs) =>
        ({ chain }) => {
          return chain()
            .insertContent({
              type: this.name,
              attrs,
            })
            .run();
        },
    };
  },

  addNodeView() {
    return ({ node, HTMLAttributes }) => {
      const span = document.createElement("span");
      span.classList.add("wiki-link");
      span.setAttribute("data-wiki-link", "");
      span.setAttribute("data-card-id", (node.attrs.cardId as string) ?? "");
      span.textContent = (node.attrs.title as string) ?? "";

      // Handle clicks
      span.addEventListener("click", (e) => {
        e.preventDefault();
        e.stopPropagation();
        const cardId = node.attrs.cardId as string;
        if (cardId && this.options.onClickLink) {
          this.options.onClickLink(cardId);
        }
      });

      Object.entries(HTMLAttributes).forEach(([key, value]) => {
        if (typeof value === "string") {
          span.setAttribute(key, value);
        }
      });

      return { dom: span };
    };
  },

  addStorage() {
    return {
      markdown: {
        serialize(state: { write: (text: string) => void }, node: { attrs: Record<string, unknown> }) {
          const title = (node.attrs.title as string) || "";
          const cardId = (node.attrs.cardId as string) || "";
          state.write(`[[${title}|${cardId}]]`);
        },
        parse: {
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          setup(markdownit: any) {
            // Register a custom inline rule for [[title|cardId]]
            // eslint-disable-next-line @typescript-eslint/no-explicit-any
            markdownit.inline.ruler.push("wiki_link", (state: any) => {
              const src = state.src;
              const pos = state.pos;
              const max = state.posMax;

              if (pos + 4 > max) return false;
              if (src.charCodeAt(pos) !== 0x5b || src.charCodeAt(pos + 1) !== 0x5b) return false;

              const closeIdx = src.indexOf("]]", pos + 2);
              if (closeIdx === -1) return false;

              const content = src.slice(pos + 2, closeIdx);
              const pipeIdx = content.indexOf("|");

              let title: string;
              let cardId: string;

              if (pipeIdx !== -1) {
                title = content.slice(0, pipeIdx);
                cardId = content.slice(pipeIdx + 1);
              } else {
                title = content;
                cardId = "";
              }

              const token = state.push("wiki_link", "", 0);
              token.attrs = [
                ["cardId", cardId],
                ["title", title],
              ];
              state.pos = closeIdx + 2;
              return true;
            });
          },
          updateDOM() { /* no-op */ },
        },
      },
    };
  },
});

/**
 * Extract all wiki-link card IDs from a TipTap JSON document.
 * Used for sync_wiki_links on save.
 */
export function extractWikiLinkCardIds(
  doc: Record<string, unknown> | null | undefined,
): number[] {
  if (!doc) return [];
  const ids: number[] = [];

  function walk(node: Record<string, unknown>) {
    if (node.type === "wikiLink" && node.attrs) {
      const attrs = node.attrs as Record<string, unknown>;
      const cardId = attrs.cardId;
      if (cardId) {
        const parsed = Number(cardId);
        if (!Number.isNaN(parsed) && parsed > 0) {
          ids.push(parsed);
        }
      }
    }
    const content = node.content as Record<string, unknown>[] | undefined;
    if (Array.isArray(content)) {
      for (const child of content) {
        walk(child);
      }
    }
  }

  walk(doc);
  return [...new Set(ids)];
}
