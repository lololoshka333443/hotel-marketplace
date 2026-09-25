import { cva, type VariantProps } from "class-variance-authority";
import type { HTMLAttributes } from "react";

import { cn } from "@/utils/cn";

const badgeVariants = cva(
  "inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-medium",
  {
    variants: {
      variant: {
        neutral: "bg-action-secondary text-text-primary",
        primary: "bg-feedback-info-bg text-feedback-info-text",
        success: "bg-feedback-success-bg text-feedback-success-text",
        warning: "bg-feedback-warning-bg text-feedback-warning-text",
        error: "bg-feedback-error-bg text-feedback-error-text",
      },
    },
    defaultVariants: { variant: "neutral" },
  },
);

export interface BadgeProps
  extends HTMLAttributes<HTMLSpanElement>,
    VariantProps<typeof badgeVariants> {}

export function Badge({ variant, className, ...rest }: BadgeProps) {
  return (
    <span className={cn(badgeVariants({ variant }), className)} {...rest} />
  );
}
