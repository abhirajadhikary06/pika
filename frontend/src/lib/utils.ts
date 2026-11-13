import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";
import { formatDistanceToNow, format } from "date-fns";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function relativeTime(iso: string) {
  try {
    return formatDistanceToNow(new Date(iso), { addSuffix: true });
  } catch {
    return iso;
  }
}

export function formatDate(iso: string) {
  try {
    return format(new Date(iso), "MMM d, yyyy HH:mm");
  } catch {
    return iso;
  }
}

export const STATUS_COLORS: Record<string, string> = {
  open: "bg-blue-100 text-blue-800",
  in_progress: "bg-amber-100 text-amber-800",
  pending: "bg-purple-100 text-purple-800",
  resolved: "bg-emerald-100 text-emerald-800",
  closed: "bg-slate-100 text-slate-600",
};

export const PRIORITY_COLORS: Record<string, string> = {
  low: "bg-slate-100 text-slate-600",
  medium: "bg-sky-100 text-sky-800",
  high: "bg-orange-100 text-orange-800",
  urgent: "bg-red-100 text-red-800",
};

export function statusLabel(s: string) {
  return s.replace("_", " ");
}
