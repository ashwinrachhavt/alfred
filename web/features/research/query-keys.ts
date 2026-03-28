export function researchQueryKey(topic: string) {
  return ["research", topic] as const;
}
