/**
 * Page shell - the standard vertical rhythm for every page.
 * Keeps measure (line length) readable on wide screens: taste/design-taste.md
 * "over-wide measure" is a slop tell.
 */

import type { ReactNode } from "react";

import { cn } from "@/utils/cn";

interface PageShellProps {
  children: ReactNode;
  className?: string;
}

export function PageShell({ children, className }: PageShellProps) {
  return (
    <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
      <div className={cn("max-w-3xl", className)}>{children}</div>
    </div>
  );
}

interface PageTitleProps {
  children: ReactNode;
  subtitle?: ReactNode;
}

export function PageTitle({ children, subtitle }: PageTitleProps) {
  return (
    <div className="mb-6">
      <h1 className="text-3xl font-bold tracking-tight">{children}</h1>
      {subtitle ? (
        <p className="mt-2 text-text-secondary">{subtitle}</p>
      ) : null}
    </div>
  );
}
