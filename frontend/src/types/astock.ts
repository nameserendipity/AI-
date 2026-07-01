export type AStockBias = "bullish" | "bearish" | "neutral" | "mixed" | "unknown";
export type AStockPreviewAction = "buy" | "sell" | "hold";

export interface AStockTechnicalView {
  latest_close?: number | null;
  ma5?: number | null;
  ma20?: number | null;
  ma60?: number | null;
  change_5d_pct?: number | null;
  change_20d_pct?: number | null;
  support?: number | null;
  resistance?: number | null;
  range_position_pct?: number | null;
  average_amplitude_pct?: number | null;
  trend: AStockBias;
}

export interface AStockSentimentView {
  bias: AStockBias;
  score: number;
  positive_hits: string[];
  negative_hits: string[];
  news_count: number;
  announcement_count: number;
}

export interface AStockAnalysisReport {
  symbol: string;
  code: string;
  exchange: string;
  name?: string | null;
  bias: AStockBias;
  confidence: number;
  summary: string;
  technical: AStockTechnicalView;
  sentiment: AStockSentimentView;
  key_points: string[];
  risk_flags: string[];
  source_status: string[];
  fetched_at: string;
}

export interface AStockStrategyPreview {
  symbol: string;
  action: AStockPreviewAction;
  proposed_action: string;
  final_items: Array<Record<string, unknown>>;
  blocked_reasons: string[];
  rationale: string;
  analysis: AStockAnalysisReport;
}

export interface AStockStrategyPreviewParams {
  symbol: string;
  initial_capital: number;
  current_position_qty: number;
  max_position_pct: number;
  open_position_pct: number;
  min_open_confidence: number;
}

export type AStockScanBucket =
  | "candidate"
  | "watch"
  | "risk"
  | "exit"
  | "skipped"
  | "error";

export interface AStockWatchlistScanItem {
  ticker: string;
  symbol?: string | null;
  display_name?: string | null;
  bucket: AStockScanBucket;
  score: number;
  action: AStockPreviewAction | "hold";
  bias: AStockBias | string;
  confidence: number;
  latest_price?: number | null;
  change_5d_pct?: number | null;
  change_20d_pct?: number | null;
  blocked_reasons: string[];
  key_points: string[];
  risk_flags: string[];
  summary: string;
  error?: string | null;
  preview?: AStockStrategyPreview | null;
}

export interface AStockWatchlistScan {
  run_id: string;
  generated_at: string;
  total: number;
  scanned: number;
  skipped: number;
  persisted_path?: string | null;
  items: AStockWatchlistScanItem[];
}

export interface AStockWatchlistScanParams {
  initial_capital: number;
  max_position_pct: number;
  open_position_pct: number;
  min_open_confidence: number;
  persist: boolean;
}

export interface AStockWatchlistSummary {
  run_id?: string | null;
  generated_at?: string | null;
  total: number;
  scanned: number;
  candidate_count: number;
  watch_count: number;
  risk_count: number;
  exit_count: number;
  skipped_count: number;
  top_candidates: AStockWatchlistScanItem[];
  risk_items: AStockWatchlistScanItem[];
  report_lines: string[];
  compact_context: string;
  source_path?: string | null;
  llm_summary?: string | null;
}

export interface AStockMemoryRun {
  run_id: string;
  market_type: string;
  analyzer_type: string;
  status: string;
  started_at?: string | null;
  completed_at?: string | null;
  interval_minutes?: number | null;
  history_limit?: number | null;
  total_items: number;
  analyzed_items: number;
  skipped_items: number;
  error_items: number;
  model_provider?: string | null;
  model_id?: string | null;
  market_summary?: string | null;
  overall_risk_level?: string | null;
  error_message?: string | null;
  metadata: Record<string, unknown>;
}

export interface AStockMemoryItem {
  id: number;
  run_id: string;
  ticker: string;
  normalized_symbol?: string | null;
  display_name?: string | null;
  market_type: string;
  analyzer_type: string;
  data_source?: string | null;
  status: string;
  skip_reason?: string | null;
  error_message?: string | null;
  trend?: string | null;
  confidence?: number | null;
  horizon?: string | null;
  reason?: string | null;
  memory_delta?: string | null;
  score?: number | null;
  action?: string | null;
  bias?: string | null;
  latest_price?: number | null;
  change_5d_pct?: number | null;
  change_20d_pct?: number | null;
  risk_flags: string[];
  key_points: string[];
  blocked_reasons: string[];
  analysis_snapshot: Record<string, unknown>;
  llm_item: Record<string, unknown>;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface AStockMemoryLatest {
  run: AStockMemoryRun | null;
  items: AStockMemoryItem[];
}
