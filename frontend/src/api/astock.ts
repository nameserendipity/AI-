import { useMutation, useQuery } from "@tanstack/react-query";
import { type ApiResponse, apiClient } from "@/lib/api-client";
import type {
  AStockMemoryLatest,
  AStockStrategyPreview,
  AStockStrategyPreviewParams,
  AStockWatchlistScan,
  AStockWatchlistScanParams,
  AStockWatchlistSummary,
} from "@/types/astock";

const buildQuery = (params: Omit<AStockStrategyPreviewParams, "symbol">) => {
  const search = new URLSearchParams({
    initial_capital: String(params.initial_capital),
    current_position_qty: String(params.current_position_qty),
    max_position_pct: String(params.max_position_pct),
    open_position_pct: String(params.open_position_pct),
    min_open_confidence: String(params.min_open_confidence),
  });
  return search.toString();
};

export const useAStockStrategyPreview = () =>
  useMutation({
    mutationFn: async (params: AStockStrategyPreviewParams) => {
      const { symbol, ...queryParams } = params;
      const response = await apiClient.get<ApiResponse<AStockStrategyPreview>>(
        `astock/${encodeURIComponent(symbol)}/strategy-preview?${buildQuery(queryParams)}`,
      );
      return response.data;
    },
  });

export const useAStockWatchlistScan = () =>
  useMutation({
    mutationFn: async (params: AStockWatchlistScanParams) => {
      const search = new URLSearchParams({
        initial_capital: String(params.initial_capital),
        max_position_pct: String(params.max_position_pct),
        open_position_pct: String(params.open_position_pct),
        min_open_confidence: String(params.min_open_confidence),
        persist: String(params.persist),
      });
      const response = await apiClient.get<ApiResponse<AStockWatchlistScan>>(
        `astock/watchlist/scan?${search.toString()}`,
      );
      return response.data;
    },
  });


export const useAStockWatchlistSummary = () =>
  useQuery({
    queryKey: ["astock", "watchlist", "summary"],
    queryFn: async () => {
      const response = await apiClient.get<ApiResponse<AStockWatchlistSummary>>(
        "astock/watchlist/summary",
      );
      return response.data;
    },
  });

export const useAStockMemoryLatest = () =>
  useQuery({
    queryKey: ["astock", "memory", "latest"],
    queryFn: async () => {
      const response = await apiClient.get<ApiResponse<AStockMemoryLatest>>(
        "astock/memory/latest?include_skipped=true&limit=100",
      );
      return response.data;
    },
  });

