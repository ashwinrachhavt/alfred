"use client";

import { Search } from "lucide-react";

import { Input } from "@/components/ui/input";
import { connectors } from "@/lib/connector-registry";

type Props = {
  activeTab: string;
  onTabChange: (tab: string) => void;
  search: string;
  onSearchChange: (val: string) => void;
};

const tabs = [{ key: "all", label: "All" }, ...connectors.map((c) => ({ key: c.key, label: c.label }))];

export function InboxFilters({ activeTab, onTabChange, search, onSearchChange }: Props) {
  return (
    <div className="space-y-3">
      <div className="flex gap-1 overflow-x-auto border-b">
        {tabs.map((tab) => (
          <button
            key={tab.key}
            onClick={() => onTabChange(tab.key)}
            className={`whitespace-nowrap px-3 py-2 text-sm font-medium transition-colors ${
              activeTab === tab.key
                ? "border-primary text-foreground border-b-2"
                : "text-muted-foreground hover:text-foreground"
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>
      <div className="relative">
        <Search className="text-muted-foreground absolute left-3 top-1/2 size-4 -translate-y-1/2" />
        <Input
          placeholder="Search your knowledge..."
          value={search}
          onChange={(e) => onSearchChange(e.target.value)}
          className="pl-9"
        />
      </div>
    </div>
  );
}
