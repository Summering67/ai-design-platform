import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"

export const cn = (...classValues: ClassValue[]) => twMerge(clsx(classValues))
