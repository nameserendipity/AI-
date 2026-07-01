import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { ApiResponse } from "@/lib/api-client";
import { apiClient } from "@/lib/api-client";

export interface FundData {
  id: number;
  user_id: string;
  name: string;
  code: string | null;
  created_at: string | null;
  updated_at: string | null;
  holdings_count: number;
  holdings?: FundHoldingData[];
}

export interface FundHoldingData {
  id: number;
  fund_id: number;
  ticker: string;
  name: string | null;
  weight: number;
  created_at: string | null;
}

export interface HoldingAnalysisData {
  ticker: string;
  name: string | null;
  weight: number;
  company_name: string | null;
  bias: string;
  confidence: number;
  score: number;
  technical_trend: string;
  sentiment_bias: string;
  summary: string | null;
  key_points: string[];
  risk_flags: string[];
  error: string | null;
}

export interface FundAnalysisData {
  fund_id: number;
  fund_name: string;
  fund_code: string | null;
  total_score: number;
  overall_bias: string;
  suggestion: string;
  weighted_confidence: number;
  holdings_analyzed: number;
  holdings_total: number;
  holding_results: HoldingAnalysisData[];
  aggregated_key_points: string[];
  aggregated_risk_flags: string[];
  analyzed_at: string;
}

export const useListFunds = () => {
  return useQuery({
    queryKey: ["funds"],
    queryFn: () => apiClient.get<ApiResponse<FundData[]>>("/fund/"),
    select: (data: ApiResponse<FundData[]>) => data.data,
  });
};

export const useGetFund = (fundId: number) => {
  return useQuery({
    queryKey: ["fund", fundId],
    queryFn: () => apiClient.get<ApiResponse<FundData>>(`/fund/${fundId}`),
    select: (data: ApiResponse<FundData>) => data.data,
    enabled: !!fundId,
  });
};

export const useAnalyzeFund = (fundId: number | null) => {
  return useQuery({
    queryKey: ["fund-analysis", fundId],
    queryFn: () =>
      apiClient.get<ApiResponse<FundAnalysisData>>(`/fund/${fundId}/analysis`),
    select: (data: ApiResponse<FundAnalysisData>) => data.data,
    enabled: !!fundId,
    retry: 1,
    staleTime: 60_000,
  });
};

export const useCreateFund = () => {
  return useMutation({
    mutationFn: (params: { name: string; code?: string }) =>
      apiClient.post<ApiResponse<FundData>>("/fund/", params),
  });
};

export const useDeleteFund = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (fundId: number) => apiClient.delete(`/fund/${fundId}`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["funds"] }),
  });
};

export const useAddHolding = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (params: {
      fundId: number;
      ticker: string;
      name?: string;
      weight: number;
    }) => apiClient.post(`/fund/${params.fundId}/holdings`, params),
    onSuccess: (_data: unknown, vars: { fundId: number }) =>
      queryClient.invalidateQueries({ queryKey: ["fund", vars.fundId] }),
  });
};

export const useRemoveHolding = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (params: { fundId: number; ticker: string }) =>
      apiClient.delete(`/fund/${params.fundId}/holdings/${params.ticker}`),
    onSuccess: (_data: unknown, vars: { fundId: number }) =>
      queryClient.invalidateQueries({ queryKey: ["fund", vars.fundId] }),
  });
};
