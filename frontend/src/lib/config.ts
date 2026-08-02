// src/lib/config.ts
const rawApiBaseUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/v1";
const trimmedApiBaseUrl = rawApiBaseUrl.replace(/\/+$/, "");

const rawDownloadAuditOutput = (process.env.NEXT_PUBLIC_DOWNLOAD_OUTPUT || "").trim().toLowerCase();
const downloadAuditOutputEnabledValues = new Set(["true", "1", "yes", "on"]);

export const API_BASE_URL = trimmedApiBaseUrl.endsWith("/v1")
	? trimmedApiBaseUrl
	: `${trimmedApiBaseUrl}/v1`;

// Default false when not provided or invalid.
export const DOWNLOAD_AUDIT_OUTPUT = downloadAuditOutputEnabledValues.has(rawDownloadAuditOutput);
