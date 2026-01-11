"use client";

import {
  MarkdownNotesEditor,
  type MarkdownNotesEditorHandle,
  type MarkdownNotesEditorProps,
} from "@/components/editor/markdown-notes-editor";

export type SystemDesignNotesEditorHandle = MarkdownNotesEditorHandle;
export type SystemDesignNotesEditorProps = MarkdownNotesEditorProps;

export const SystemDesignNotesEditor = MarkdownNotesEditor;
SystemDesignNotesEditor.displayName = "SystemDesignNotesEditor";
