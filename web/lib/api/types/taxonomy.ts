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
