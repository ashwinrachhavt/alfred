export type TaxonomyNode = {
  id: number;
  slug: string;
  display_name: string;
  level: number;
  parent_slug: string | null;
  description: string | null;
  sort_order: number;
};

export type TaxonomyTreeNode = {
  slug: string;
  display_name: string;
  level: number;
  doc_count: number;
  children: TaxonomyTreeNode[];
};

export type CreateTaxonomyNodePayload = {
  name: string;
  level: number;
  parent_slug?: string | null;
  description?: string | null;
};

export type UpdateTaxonomyNodePayload = {
  name?: string;
  parent_slug?: string | null;
  description?: string | null;
};

export type DeleteTaxonomyNodeResponse = {
  deleted_slug: string;
  children_reassigned: number;
};
