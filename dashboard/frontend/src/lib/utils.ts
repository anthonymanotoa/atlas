import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

// shadcn-style class merger: clsx for conditional logic + tailwind-merge so later
// utility classes win over earlier ones (essential once cva base classes meet overrides).
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}
