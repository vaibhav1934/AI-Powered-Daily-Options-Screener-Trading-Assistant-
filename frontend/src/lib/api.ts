// src/lib/api.ts
import { API_BASE_URL } from "./config";

export interface ScanResult {
  id: number;
  ticker: string;
  score: number;
  risk_bucket: string;
  list_type: string;
  status: string;
  gap?: string; // Derived or fetched later
  price?: string; // Derived or fetched later
  veto_rule?: string;
  veto_reason?: string;
  execution_details?: {
    entry_price?: number;
    strike_price?: number;
    stop_loss?: number;
  };
}

export interface WatchlistResponse {
  scan_date: string;
  total_results: number;
  risk_distribution: Record<string, number>;
  cutoff_status: {
    is_past_cutoff: boolean;
    cutoff_time_cst: string;
    current_time_cst: string;
  };
  results: ScanResult[];
}

export async function fetchWatchlist(date?: string): Promise<WatchlistResponse> {
  const url = new URL(`${API_BASE_URL}/watchlist`);
  if (date) {
    url.searchParams.append("scan_date", date);
  }

  const res = await fetch(url.toString(), {
    headers: {
      "Content-Type": "application/json",
      // Include dummy API key if required by backend, since we haven't implemented real auth yet
      "X-API-Key": "dev_key",
    },
    cache: 'no-store'
  });

  if (!res.ok) {
    throw new Error(`Failed to fetch watchlist: ${res.status}`);
  }

  return res.json();
}

export async function triggerScan(): Promise<any> {
  const res = await fetch(`${API_BASE_URL}/scans/trigger`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-API-Key": "dev_key",
    },
  });

  if (!res.ok) {
    throw new Error(`Failed to trigger scan: ${res.status}`);
  }

  return res.json();
}

export async function fetchScorecard(date?: string): Promise<any> {
  if (!date) {
    date = new Date().toISOString().split('T')[0];
  }
  const url = new URL(`${API_BASE_URL}/admin/scorecard/${date}`);

  const res = await fetch(url.toString(), {
    headers: {
      "X-API-Key": "dev_key",
    },
  });

  if (!res.ok) {
    throw new Error(`Failed to fetch scorecard: ${res.status}`);
  }

  return res.json();
}

export async function uploadScreenshot(scanId: number, file: File): Promise<any> {
  const formData = new FormData();
  formData.append("file", file);

  const res = await fetch(`${API_BASE_URL}/screenshots/${scanId}`, {
    method: "POST",
    headers: {
      "X-API-Key": "dev_key",
    },
    body: formData,
  });

  if (!res.ok) {
    throw new Error(`Upload failed: ${res.status}`);
  }

  const data = await res.json();
  
  // Immediately confirm it to unlock execution details
  const confirmRes = await fetch(`${API_BASE_URL}/screenshots/${data.id}/confirm`, {
    method: "POST",
    headers: {
      "X-API-Key": "dev_key",
    }
  });

  if (!confirmRes.ok) {
    throw new Error(`Confirm failed: ${confirmRes.status}`);
  }

  return confirmRes.json();
}

export async function uploadPortfolio(file: File): Promise<any> {
  const formData = new FormData();
  formData.append("file", file);

  const res = await fetch(`${API_BASE_URL}/portfolio/upload`, {
    method: "POST",
    headers: {
      "X-API-Key": "dev_key",
    },
    body: formData,
  });

  if (!res.ok) {
    const err = await res.text();
    throw new Error(`Portfolio upload failed: ${err}`);
  }

  return res.json();
}
