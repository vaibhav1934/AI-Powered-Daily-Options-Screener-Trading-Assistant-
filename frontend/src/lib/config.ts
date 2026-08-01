// src/lib/config.ts
const rawApiBaseUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8001/v1";
const trimmedApiBaseUrl = rawApiBaseUrl.replace(/\/+$/, "");

export const API_BASE_URL = trimmedApiBaseUrl.endsWith("/v1")
	? trimmedApiBaseUrl
	: `${trimmedApiBaseUrl}/v1`;
