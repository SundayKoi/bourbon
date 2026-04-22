import type { Listing } from "../lib/api";

const SOURCE_LABELS: Record<string, string> = {
  unicorn_auctions: "Unicorn Auctions",
  virginia_abc: "Virginia ABC",
  breaking_bourbon: "Breaking Bourbon",
  reddit: "Reddit",
  seelbachs: "Seelbachs",
  caskers: "Caskers",
  whisky_auctioneer: "Whisky Auctioneer",
};

const SOURCE_COLORS: Record<string, string> = {
  unicorn_auctions: "bg-purple-100 text-purple-800",
  virginia_abc: "bg-blue-100 text-blue-800",
  breaking_bourbon: "bg-green-100 text-green-800",
  reddit: "bg-orange-100 text-orange-800",
  seelbachs: "bg-amber-100 text-amber-800",
  caskers: "bg-gray-100 text-gray-800",
  whisky_auctioneer: "bg-pink-100 text-pink-800",
};

function formatEndsAt(ends: string | null): string | null {
  if (!ends) return null;
  const d = new Date(ends);
  const diffMs = d.getTime() - Date.now();
  if (diffMs < 0) return "Ended";
  const hours = Math.floor(diffMs / (1000 * 60 * 60));
  const days = Math.floor(hours / 24);
  if (days > 0) return `Ends in ${days}d ${hours % 24}h`;
  if (hours > 0) return `Ends in ${hours}h`;
  const mins = Math.floor(diffMs / (1000 * 60));
  return `Ends in ${mins}m`;
}

export function ListingCard({ listing }: { listing: Listing }) {
  const sourceLabel = SOURCE_LABELS[listing.source] || listing.source;
  const sourceColor =
    SOURCE_COLORS[listing.source] || "bg-gray-100 text-gray-800";
  const endsLabel = formatEndsAt(listing.ends_at);

  return (
    <a
      href={listing.url}
      target="_blank"
      rel="noreferrer"
      className="group block bg-white rounded-lg shadow-sm hover:shadow-md transition-shadow overflow-hidden border border-bourbon-100"
    >
      <div className="aspect-square bg-bourbon-50 relative overflow-hidden">
        {listing.image_url ? (
          <img
            src={listing.image_url}
            alt={listing.title}
            className="w-full h-full object-cover group-hover:scale-105 transition-transform"
            loading="lazy"
            onError={(e) => {
              (e.target as HTMLImageElement).style.display = "none";
            }}
          />
        ) : (
          <div className="w-full h-full flex items-center justify-center text-bourbon-500">
            <svg
              className="w-16 h-16"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={1.5}
                d="M9 3v2m6-2v2M9 19v2m6-2v2M5 9H3m2 6H3m18-6h-2m2 6h-2M7 19h10a2 2 0 002-2V7a2 2 0 00-2-2H7a2 2 0 00-2 2v10a2 2 0 002 2z"
              />
            </svg>
          </div>
        )}
        {listing.watchlist_match && (
          <div className="absolute top-2 right-2 bg-bourbon-500 text-white text-xs px-2 py-1 rounded-full font-medium">
            Watchlist
          </div>
        )}
      </div>
      <div className="p-4 space-y-2">
        <span
          className={`inline-block text-xs px-2 py-0.5 rounded ${sourceColor}`}
        >
          {sourceLabel}
        </span>
        <h3 className="text-sm font-medium text-bourbon-900 line-clamp-2 min-h-[2.5rem]">
          {listing.title}
        </h3>
        <div className="flex items-baseline justify-between gap-2 pt-1">
          <span className="text-lg font-semibold text-bourbon-700">
            {listing.price !== null
              ? `$${listing.price.toLocaleString(undefined, {
                  minimumFractionDigits: 2,
                  maximumFractionDigits: 2,
                })}`
              : "—"}
          </span>
          {endsLabel && (
            <span className="text-xs text-red-600 font-medium">
              {endsLabel}
            </span>
          )}
        </div>
      </div>
    </a>
  );
}
