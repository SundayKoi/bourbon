const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

export type Listing = {
  id: number;
  source: string;
  external_id: string;
  title: string;
  url: string;
  price: number | null;
  image_url: string | null;
  ends_at: string | null;
  discovered_at: string;
  watchlist_match: boolean;
};

export type WatchlistItem = {
  id: number;
  keyword: string;
  created_at: string;
  active: boolean;
};

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const resp = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers || {}) },
  });
  if (!resp.ok) {
    throw new Error(`${resp.status} ${resp.statusText}`);
  }
  if (resp.status === 204) return undefined as T;
  return resp.json();
}

export const api = {
  listings: (params: { source?: string; watchlist_only?: boolean } = {}) => {
    const qs = new URLSearchParams();
    if (params.source) qs.set("source", params.source);
    if (params.watchlist_only) qs.set("watchlist_only", "true");
    qs.set("limit", "500");
    return request<Listing[]>(`/listings?${qs}`);
  },
  watchlist: () => request<WatchlistItem[]>("/watchlist"),
  addKeyword: (keyword: string) =>
    request<WatchlistItem>("/watchlist", {
      method: "POST",
      body: JSON.stringify({ keyword }),
    }),
  removeKeyword: (id: number) =>
    request<void>(`/watchlist/${id}`, { method: "DELETE" }),
  sources: () => request<string[]>("/sources"),
};
