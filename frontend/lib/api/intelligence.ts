import { apiPostJson } from "@/lib/api/client";
import { apiRoutes } from "@/lib/api/routes";
import type {
  AutocompleteRequest,
  AutocompleteResponse,
  TextEditRequest,
  TextEditResponse,
} from "@/lib/api/types/intelligence";

export function autocompleteText(payload: AutocompleteRequest): Promise<AutocompleteResponse> {
  return apiPostJson<AutocompleteResponse, AutocompleteRequest>(apiRoutes.intelligence.autocomplete, payload, {
    cache: "no-store",
  });
}

export function editText(payload: TextEditRequest): Promise<TextEditResponse> {
  return apiPostJson<TextEditResponse, TextEditRequest>(apiRoutes.intelligence.edit, payload, {
    cache: "no-store",
  });
}

