export type DashboardWidgetKey =
  | "recent-documents"
  | "company-research"
  | "threads"
  | "follow-ups"
  | "templates";

export const DASHBOARD_LAYOUT_STORAGE_KEY = "alfred:dashboard:layout:v1";

type StoredDashboardLayout = {
  version: 1;
  order: DashboardWidgetKey[];
  hidden: DashboardWidgetKey[];
};

export type DashboardLayout = {
  order: DashboardWidgetKey[];
  hidden: Set<DashboardWidgetKey>;
};

const DEFAULT_ORDER: DashboardWidgetKey[] = [
  "recent-documents",
  "company-research",
  "threads",
  "follow-ups",
  "templates",
];

function uniq<T>(list: T[]): T[] {
  return Array.from(new Set(list));
}

export function defaultDashboardLayout(): DashboardLayout {
  return {
    order: DEFAULT_ORDER,
    hidden: new Set(),
  };
}

export function loadDashboardLayout(
  allowedKeys: DashboardWidgetKey[] = DEFAULT_ORDER,
): DashboardLayout {
  if (typeof window === "undefined") return defaultDashboardLayout();

  const raw = window.localStorage.getItem(DASHBOARD_LAYOUT_STORAGE_KEY);
  if (!raw) return defaultDashboardLayout();

  try {
    const parsed = JSON.parse(raw) as unknown;
    if (!parsed || typeof parsed !== "object") return defaultDashboardLayout();
    const payload = parsed as Partial<StoredDashboardLayout>;
    if (payload.version !== 1) return defaultDashboardLayout();

    const allowed = new Set(allowedKeys);
    const order = uniq(
      Array.isArray(payload.order) ? (payload.order as DashboardWidgetKey[]) : DEFAULT_ORDER,
    ).filter((key) => allowed.has(key));

    const missing = allowedKeys.filter((key) => !order.includes(key));
    const nextOrder = [...order, ...missing];

    const hidden = new Set(
      uniq(Array.isArray(payload.hidden) ? (payload.hidden as DashboardWidgetKey[]) : []).filter(
        (key) => allowed.has(key),
      ),
    );

    return { order: nextOrder, hidden };
  } catch {
    return defaultDashboardLayout();
  }
}

export function saveDashboardLayout(layout: DashboardLayout): void {
  if (typeof window === "undefined") return;

  const payload: StoredDashboardLayout = {
    version: 1,
    order: layout.order,
    hidden: Array.from(layout.hidden),
  };

  window.localStorage.setItem(DASHBOARD_LAYOUT_STORAGE_KEY, JSON.stringify(payload));
}
