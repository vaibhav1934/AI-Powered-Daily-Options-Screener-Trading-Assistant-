// src/lib/config.ts
const isProduction = process.env.NODE_ENV === "production";
const rawApiBaseUrl = (process.env.NEXT_PUBLIC_API_URL || "").trim();
const fallbackDevApiBaseUrl = "http://localhost:8000/v1";
const effectiveRawApiBaseUrl = rawApiBaseUrl || (isProduction ? "" : fallbackDevApiBaseUrl);
const trimmedApiBaseUrl = effectiveRawApiBaseUrl.replace(/\/+$/, "");

const rawDownloadAuditOutput = (process.env.NEXT_PUBLIC_DOWNLOAD_OUTPUT || "").trim().toLowerCase();
const downloadAuditOutputEnabledValues = new Set(["true", "1", "yes", "on"]);

export const API_BASE_URL = trimmedApiBaseUrl.endsWith("/v1")
	? trimmedApiBaseUrl
	: (trimmedApiBaseUrl ? `${trimmedApiBaseUrl}/v1` : "");

export const API_BASE_URL_ERROR = API_BASE_URL
	? null
	: "Missing NEXT_PUBLIC_API_URL in production. Set NEXT_PUBLIC_API_URL to your backend origin (for example: https://api.yourdomain.com).";

// Default false when not provided or invalid.
export const DOWNLOAD_AUDIT_OUTPUT = downloadAuditOutputEnabledValues.has(rawDownloadAuditOutput);
