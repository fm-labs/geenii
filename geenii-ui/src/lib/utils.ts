import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

/** Join a base url and a path, independent of trailing/leading slashes. */
export function joinUrl(baseUrl: string, path: string) {
  return baseUrl.replace(/\/+$/, '') + '/' + path.replace(/^\/+/, '')
}
