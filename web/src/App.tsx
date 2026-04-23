import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "./lib/api";
import { ListingCard } from "./components/ListingCard";
import { Watchlist } from "./components/Watchlist";

export default function App() {
  const [source, setSource] = useState<string>("");
  const [watchlistOnly, setWatchlistOnly] = useState(false);
  const [minPrice, setMinPrice] = useState<string>("");
  const [maxPrice, setMaxPrice] = useState<string>("");

  const { data: sources = [] } = useQuery({
    queryKey: ["sources"],
    queryFn: api.sources,
  });

  const minPriceNum = minPrice === "" ? undefined : Number(minPrice);
  const maxPriceNum = maxPrice === "" ? undefined : Number(maxPrice);

  const { data: listings = [], isLoading } = useQuery({
    queryKey: ["listings", source, watchlistOnly, minPriceNum, maxPriceNum],
    queryFn: () =>
      api.listings({
        source: source || undefined,
        watchlist_only: watchlistOnly,
        min_price: minPriceNum,
        max_price: maxPriceNum,
      }),
  });

  return (
    <div className="min-h-screen">
      <header className="bg-bourbon-900 text-bourbon-50 py-6 shadow-md">
        <div className="max-w-7xl mx-auto px-4 flex items-baseline justify-between">
          <h1 className="text-3xl font-display">🥃 Bourbon Alerts</h1>
          <p className="text-sm opacity-75">
            {listings.length} active {listings.length === 1 ? "listing" : "listings"}
          </p>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 py-6 grid grid-cols-1 lg:grid-cols-4 gap-6">
        <aside className="lg:col-span-1 space-y-4">
          <div className="bg-white rounded-lg shadow-sm border border-bourbon-100 p-4">
            <h2 className="text-lg font-display font-semibold text-bourbon-900 mb-3">
              Filters
            </h2>

            <label className="flex items-center gap-2 mb-3 text-sm text-bourbon-900 cursor-pointer">
              <input
                type="checkbox"
                checked={watchlistOnly}
                onChange={(e) => setWatchlistOnly(e.target.checked)}
                className="rounded"
              />
              Watchlist only
            </label>

            <label className="block text-sm text-bourbon-900 mb-1">Source</label>
            <select
              value={source}
              onChange={(e) => setSource(e.target.value)}
              className="w-full px-2 py-1.5 border border-bourbon-100 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-bourbon-500 mb-3"
            >
              <option value="">All sources</option>
              {sources.map((s) => (
                <option key={s} value={s}>
                  {s.replace(/_/g, " ")}
                </option>
              ))}
            </select>

            <label className="block text-sm text-bourbon-900 mb-1">Price</label>
            <div className="flex items-center gap-2">
              <div className="relative flex-1">
                <span className="absolute left-2 top-1/2 -translate-y-1/2 text-bourbon-700 text-sm">
                  $
                </span>
                <input
                  type="number"
                  inputMode="decimal"
                  min={0}
                  step="1"
                  value={minPrice}
                  onChange={(e) => setMinPrice(e.target.value)}
                  placeholder="Min"
                  className="w-full pl-5 pr-2 py-1.5 border border-bourbon-100 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-bourbon-500"
                />
              </div>
              <span className="text-bourbon-700 text-sm">–</span>
              <div className="relative flex-1">
                <span className="absolute left-2 top-1/2 -translate-y-1/2 text-bourbon-700 text-sm">
                  $
                </span>
                <input
                  type="number"
                  inputMode="decimal"
                  min={0}
                  step="1"
                  value={maxPrice}
                  onChange={(e) => setMaxPrice(e.target.value)}
                  placeholder="Max"
                  className="w-full pl-5 pr-2 py-1.5 border border-bourbon-100 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-bourbon-500"
                />
              </div>
            </div>
            {(minPrice || maxPrice) && (
              <button
                onClick={() => {
                  setMinPrice("");
                  setMaxPrice("");
                }}
                className="mt-2 text-xs text-bourbon-700 hover:text-bourbon-900 underline"
              >
                Clear price
              </button>
            )}
          </div>

          <Watchlist />
        </aside>

        <section className="lg:col-span-3">
          {isLoading ? (
            <p className="text-bourbon-700">Loading listings…</p>
          ) : listings.length === 0 ? (
            <p className="text-bourbon-700 italic">No active listings.</p>
          ) : (
            <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
              {listings.map((listing) => (
                <ListingCard key={listing.id} listing={listing} />
              ))}
            </div>
          )}
        </section>
      </main>
    </div>
  );
}
