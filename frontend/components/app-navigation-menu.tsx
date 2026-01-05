"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { appTopNavItems } from "@/lib/navigation";

import {
  NavigationMenu,
  NavigationMenuItem,
  NavigationMenuLink,
  NavigationMenuList,
  navigationMenuTriggerStyle,
} from "@/components/ui/navigation-menu";

export function AppNavigationMenu({ className }: { className?: string }) {
  const pathname = usePathname();

  return (
    <NavigationMenu className={className}>
      <NavigationMenuList>
        {appTopNavItems.map((item) => (
          <NavigationMenuItem key={item.key}>
            <NavigationMenuLink asChild className={navigationMenuTriggerStyle()}>
              <Link href={item.href} aria-current={pathname === item.href ? "page" : undefined}>
                {item.title}
              </Link>
            </NavigationMenuLink>
          </NavigationMenuItem>
        ))}
      </NavigationMenuList>
    </NavigationMenu>
  );
}
