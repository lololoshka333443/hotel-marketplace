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
    <div className="mb-10">
      <h1 className="font-serif text-4xl font-normal leading-display tracking-tight">
        {children}
      </h1>
      {subtitle ? (
        <p className="mt-4 text-lg leading-normal text-text-secondary">{subtitle}</p>
      ) : null}
    </div>
  );
}
