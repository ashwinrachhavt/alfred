import { Extension } from "@tiptap/core";
import { Plugin, PluginKey } from "@tiptap/pm/state";

type BlockIdOptions = {
  types: string[];
  attributeName: string;
  disabled?: boolean;
};

function createBlockId(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  return `block-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;
}

export const BlockId = Extension.create<BlockIdOptions>({
  name: "blockId",

  addOptions() {
    return {
      types: [],
      attributeName: "blockId",
      disabled: false,
    };
  },

  addGlobalAttributes() {
    return [
      {
        types: this.options.types,
        attributes: {
          [this.options.attributeName]: {
            default: null,
            parseHTML: (element) => element.getAttribute("data-block-id"),
            renderHTML: (attributes) => {
              const value = attributes[this.options.attributeName];
              return typeof value === "string" && value.length > 0
                ? { "data-block-id": value }
                : {};
            },
          },
        },
      },
    ];
  },

  addProseMirrorPlugins() {
    const { attributeName, disabled, types } = this.options;

    return [
      new Plugin({
        key: new PluginKey("alfred-block-id"),
        appendTransaction(transactions, _oldState, newState) {
          if (disabled) return null;
          if (!transactions.some((transaction) => transaction.docChanged)) return null;

          let transaction = newState.tr;
          let changed = false;

          newState.doc.descendants((node, pos) => {
            if (!types.includes(node.type.name)) return true;
            const currentId = node.attrs[attributeName];
            if (typeof currentId === "string" && currentId.length > 0) return true;

            transaction = transaction.setNodeMarkup(pos, undefined, {
              ...node.attrs,
              [attributeName]: createBlockId(),
            });
            changed = true;
            return true;
          });

          return changed ? transaction : null;
        },
      }),
    ];
  },
});
