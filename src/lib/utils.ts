import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}

export function formatBytes(bytes: number, decimals = 1): string {
  if (!bytes || bytes <= 0) return "0 B";
  const k = 1024;
  const dm = decimals < 0 ? 0 : decimals;
  const sizes = ["B", "KB", "MB", "GB", "TB", "PB"];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  const safeI = Math.min(i, sizes.length - 1);
  return `${parseFloat((bytes / Math.pow(k, safeI)).toFixed(dm))} ${sizes[safeI]}`;
}

export function formatNumber(num: number): string {
  return new Intl.NumberFormat().format(num || 0);
}

export function formatDate(dateStr?: string | null): string {
  if (!dateStr) return "-";
  try {
    const d = new Date(dateStr);
    if (isNaN(d.getTime())) return dateStr;
    return d.toLocaleString(undefined, {
      year: "numeric",
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return dateStr;
  }
}

export type GroupingMode = "project" | "leaf" | "top" | "flat";

/**
 * Extracts a grouped folder path based on grouping mode:
 * - "project" (default): Groups by meaningful project/base folder (e.g. "Compressed/HelloFace-main" or "Documents").
 *   If path has >= 2 directory parts, returns the first 2 parts (e.g. "Compressed/HelloFace-main").
 *   If path has 1 directory part, returns that part (e.g. "Documents").
 *   If path is directly in root, returns "/".
 * - "top": 1st directory level only (e.g. "Compressed").
 * - "leaf": exact immediate parent directory (e.g. "Compressed/HelloFace-main/platforms/Android").
 * - "flat": always "/" (no folder hierarchy).
 */
export function getFolderByMode(
  relativePath?: string | null,
  mode: GroupingMode = "project"
): string {
  if (!relativePath || mode === "flat") return "/";
  const normalized = relativePath.replace(/\\/g, "/").trim();
  const parts = normalized.split("/").filter(Boolean);
  if (parts.length <= 1) {
    return "/";
  }

  const dirParts = parts.slice(0, -1);
  if (dirParts.length === 0) return "/";

  if (mode === "top") {
    return dirParts[0];
  }

  if (mode === "project") {
    if (dirParts.length >= 2) {
      return `${dirParts[0]}/${dirParts[1]}`;
    }
    return dirParts[0];
  }

  // mode === "leaf"
  return dirParts.join("/");
}

/**
 * Extracts the top-level parent project folder of a given path:
 * e.g. "Compressed/HelloFace-main/platforms/Android" -> "Compressed/HelloFace-main"
 */
export function getTopProjectFolder(path?: string | null): string {
  if (!path || path === "/") return "/";
  const normalized = path.replace(/\\/g, "/").trim();
  const parts = normalized.split("/").filter(Boolean);
  if (parts.length <= 1) return parts[0] || "/";
  return `${parts[0]}/${parts[1]}`;
}

/**
 * Extracts the parent folder from a relative path (legacy/leaf compatibility)
 */
export function getParentFolder(relativePath?: string | null): string {
  return getFolderByMode(relativePath, "leaf");
}


