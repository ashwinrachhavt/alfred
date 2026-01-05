export function companyResearchQueryKey(company: string) {
  return ["company", "research", company] as const;
}
