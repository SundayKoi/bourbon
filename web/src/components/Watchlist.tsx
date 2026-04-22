import { useState } from "react";
import {
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import { api } from "../lib/api";

export function Watchlist() {
  const queryClient = useQueryClient();
  const [newKeyword, setNewKeyword] = useState("");

  const { data: watchlist = [], isLoading } = useQuery({
    queryKey: ["watchlist"],
    queryFn: api.watchlist,
  });

  const addMutation = useMutation({
    mutationFn: api.addKeyword,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["watchlist"] });
      setNewKeyword("");
    },
  });

  const removeMutation = useMutation({
    mutationFn: api.removeKeyword,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["watchlist"] });
    },
  });

  const active = watchlist.filter((w) => w.active);

  return (
    <div className="bg-white rounded-lg shadow-sm border border-bourbon-100 p-4">
      <h2 className="text-lg font-display font-semibold text-bourbon-900 mb-3">
        Watchlist
      </h2>

      <form
        onSubmit={(e) => {
          e.preventDefault();
          const kw = newKeyword.trim();
          if (kw) addMutation.mutate(kw);
        }}
        className="flex gap-2 mb-4"
      >
        <input
          type="text"
          value={newKeyword}
          onChange={(e) => setNewKeyword(e.target.value)}
          placeholder="Add keyword (e.g. Weller 12)"
          className="flex-1 px-3 py-2 border border-bourbon-100 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-bourbon-500"
        />
        <button
          type="submit"
          disabled={!newKeyword.trim() || addMutation.isPending}
          className="px-4 py-2 bg-bourbon-500 text-white rounded-md text-sm font-medium hover:bg-bourbon-700 disabled:opacity-50"
        >
          Add
        </button>
      </form>

      {isLoading ? (
        <p className="text-sm text-bourbon-700">Loading…</p>
      ) : (
        <ul className="space-y-1 max-h-96 overflow-y-auto">
          {active.length === 0 && (
            <li className="text-sm text-bourbon-700 italic">
              No keywords yet.
            </li>
          )}
          {active.map((w) => (
            <li
              key={w.id}
              className="flex items-center justify-between text-sm py-1 px-2 rounded hover:bg-bourbon-50 group"
            >
              <span className="text-bourbon-900">{w.keyword}</span>
              <button
                onClick={() => removeMutation.mutate(w.id)}
                className="text-red-600 opacity-0 group-hover:opacity-100 transition-opacity text-xs"
                title="Remove"
              >
                Remove
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
