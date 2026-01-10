export type AutocompleteRequest = {
  text: string;
  tone?: string | null;
  max_chars?: number;
};

export type AutocompleteResponse = {
  completion: string;
  language?: string | null;
};

export type TextEditRequest = {
  text: string;
  instruction: string;
  tone?: string | null;
};

export type TextEditResponse = {
  output: string;
  language?: string | null;
};

