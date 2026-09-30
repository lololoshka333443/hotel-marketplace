import { cva, type VariantProps } from "class-variance-authority";
import type { HTMLAttributes } from "react";

import { cn } from "@/utils/cn";

// A status mark, not a chip: hairline border, the state in the type color, no
// fill. The brief's mood has no loud pills — status reads from the letterform.
const badgeVariants = cva(
  "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-[11px] font-medium uppercase tracking-eyebrow",
  {
    variants: {
      variant: {
        neutral: "border-border-strong text-text-secondary",
        primary: "border-border-strong text-text-primary",
        success: "border-border-strong text-feedback-success-text",
        warning: "border-border-strong text-feedback-warning-text",
        error: "border-border-strong text-feedback-error-text",
      },
    },
    defaultVariants: { variant: "neutral" },
  },
);

export interface BadgeProps
  extends HTMLAttributes<HTMLSpanElement>,
    VariantProps<typeof badgeVariants> {}

export function Badge({ variant, className, ...rest }: BadgeProps) {
  return <span className={cn(badgeVariants({ variant }), className)} {...rest} />;
}
