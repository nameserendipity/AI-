import {
  AlertTriangle,
  Archive,
  BarChart3,
  CheckCircle2,
  Loader2,
  Radar,
  ShieldAlert,
} from "lucide-react";
import { useMemo, useState } from "react";
import { Link } from "react-router";
import {
  useAStockWatchlistScan,
  useAStockWatchlistSummary,
} from "@/api/astock";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";
import type { AStockScanBucket, AStockWatchlistScanItem } from "@/types/astock";

const bucketCopy: Record<AStockScanBucket, string> = {
  candidate: "Candidate",
  watch: "Watch",
  risk: "Risk",
  exit: "Exit",
  skipped: "Skipped",
  error: "Error",
};

const bucketClass: Record<AStockScanBucket, string> = {
  candidate:
    "border-emerald-500/30 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300",
  watch: "border-zinc-500/20 bg-zinc-500/10 text-zinc-700 dark:text-zinc-300",
  risk: "border-amber-500/30 bg-amber-500/10 text-amber-700 dark:text-amber-300",
  exit: "border-rose-500/30 bg-rose-500/10 text-rose-700 dark:text-rose-300",
  skipped: "border-border bg-muted text-muted-foreground",
  error: "border-rose-500/30 bg-rose-500/10 text-rose-700 dark:text-rose-300",
};

function formatNumber(value?: number | null, digits = 2) {
  if (value === null || value === undefined || Number.isNaN(value)) return "--";
  return value.toFixed(digits);
}

function formatPercent(value?: number | null) {
  if (value === null || value === undefined || Number.isNaN(value)) return "--";
  return `${value.toFixed(2)}%`;
}

function ScanSkeleton() {
  return (
    <div className="grid gap-3">
      <Skeleton className="h-28 rounded-xl" />
      <Skeleton className="h-28 rounded-xl" />
      <Skeleton className="h-28 rounded-xl" />
    </div>
  );
}

function ScanItemCard({ item }: { item: AStockWatchlistScanItem }) {
  return (
    <Card className="overflow-hidden border-border/80 shadow-none">
      <CardContent className="grid gap-4 p-4 lg:grid-cols-[1fr_130px_130px] lg:items-center">
        <div className="min-w-0">
          <div className="mb-2 flex flex-wrap items-center gap-2">
            <Badge className={cn("border", bucketClass[item.bucket])}>
              {bucketCopy[item.bucket]}
            </Badge>
            <span className="font-semibold text-lg">
              {item.display_name || item.ticker}
            </span>
            <span className="text-muted-foreground text-sm">
              {item.symbol || item.ticker}
            </span>
          </div>
          <p className="line-clamp-2 text-muted-foreground text-sm leading-6">
            {item.summary || item.error || "No summary yet."}
          </p>
          <div className="mt-3 flex flex-wrap gap-2">
            {item.key_points.slice(0, 2).map((point) => (
              <span
                className="rounded-full border bg-background px-2.5 py-1 text-muted-foreground text-xs"
                key={point}
              >
                {point}
              </span>
            ))}
          </div>
        </div>

        <div className="grid grid-cols-3 gap-2 text-sm lg:grid-cols-1">
          <div>
            <div className="text-muted-foreground text-xs">Price</div>
            <div className="font-semibold">{formatNumber(item.latest_price)}</div>
          </div>
          <div>
            <div className="text-muted-foreground text-xs">5D</div>
            <div className="font-semibold">{formatPercent(item.change_5d_pct)}</div>
          </div>
          <div>
            <div className="text-muted-foreground text-xs">20D</div>
            <div className="font-semibold">{formatPercent(item.change_20d_pct)}</div>
          </div>
        </div>

        <div className="flex items-center justify-between gap-3 lg:flex-col lg:items-end">
          <div className="text-right">
            <div className="text-muted-foreground text-xs">Score / Confidence</div>
            <div className="font-semibold text-2xl">
              {formatNumber(item.score, 0)}
              <span className="ml-2 text-muted-foreground text-sm">
                {Math.round(item.confidence * 100)}%
              </span>
            </div>
          </div>
          {item.symbol ? (
            <Button asChild size="sm" variant="secondary">
              <Link to={`/home/astock-preview?symbol=${encodeURIComponent(item.symbol)}`}>
                Open preview
              </Link>
            </Button>
          ) : null}
        </div>

        {(item.risk_flags.length > 0 || item.blocked_reasons.length > 0) && (
          <div className="rounded-lg border border-amber-500/20 bg-amber-500/5 p-3 text-amber-700 text-sm dark:text-amber-300 lg:col-span-3">
            {[...item.risk_flags, ...item.blocked_reasons].slice(0, 3).join("; ")}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

export default function AStockWatchlistScanPage() {
  const [initialCapital, setInitialCapital] = useState(100000);
  const [maxPositionPct, setMaxPositionPct] = useState(0.3);
  const [openPositionPct, setOpenPositionPct] = useState(0.1);
  const scanMutation = useAStockWatchlistScan();
  const summaryQuery = useAStockWatchlistSummary();
  const result = scanMutation.data;
  const summary = summaryQuery.data;

  const groups = useMemo(() => {
    const base: Record<AStockScanBucket, AStockWatchlistScanItem[]> = {
      candidate: [],
      watch: [],
      risk: [],
      exit: [],
      skipped: [],
      error: [],
    };
    for (const item of result?.items ?? []) {
      base[item.bucket].push(item);
    }
    return base;
  }, [result]);

  const runScan = () => {
    scanMutation.mutate(
      {
        initial_capital: initialCapital,
        max_position_pct: maxPositionPct,
        open_position_pct: openPositionPct,
        min_open_confidence: 0.6,
        persist: true,
      },
      {
        onSuccess: () => {
          summaryQuery.refetch();
        },
      },
    );
  };

  return (
    <div className="scroll-container h-full bg-card px-6 py-6">
      <section className="mx-auto flex max-w-6xl flex-col gap-6">
        <div className="rounded-2xl border bg-background p-6 shadow-sm">
          <div className="grid gap-6 lg:grid-cols-[1fr_420px] lg:items-end">
            <div>
              <div className="mb-3 inline-flex items-center gap-2 rounded-full border bg-muted/40 px-3 py-1 text-muted-foreground text-xs">
                <Radar className="size-3.5" />
                Watchlist batch scan
              </div>
              <h1 className="font-semibold text-3xl tracking-tight">
                Turn your watchlist into a daily candidate pool
              </h1>
              <p className="mt-3 max-w-2xl text-muted-foreground text-sm leading-6">
                Scan A-share watchlist items, persist compact analysis memory, and
                summarize the current decision layer.
              </p>
            </div>

            <div className="grid gap-3 rounded-xl border bg-muted/20 p-4">
              <div className="grid grid-cols-3 gap-3">
                <div className="grid gap-1.5">
                  <Label htmlFor="scan-capital">Capital</Label>
                  <Input
                    id="scan-capital"
                    type="number"
                    value={initialCapital}
                    onChange={(event) =>
                      setInitialCapital(Number(event.target.value || 0))
                    }
                  />
                </div>
                <div className="grid gap-1.5">
                  <Label htmlFor="scan-max">Max</Label>
                  <Input
                    id="scan-max"
                    type="number"
                    step="0.01"
                    value={maxPositionPct}
                    onChange={(event) =>
                      setMaxPositionPct(Number(event.target.value || 0))
                    }
                  />
                </div>
                <div className="grid gap-1.5">
                  <Label htmlFor="scan-open">Entry</Label>
                  <Input
                    id="scan-open"
                    type="number"
                    step="0.01"
                    value={openPositionPct}
                    onChange={(event) =>
                      setOpenPositionPct(Number(event.target.value || 0))
                    }
                  />
                </div>
              </div>
              <Button onClick={runScan} disabled={scanMutation.isPending}>
                {scanMutation.isPending ? (
                  <Loader2 className="size-4 animate-spin" />
                ) : (
                  <Radar className="size-4" />
                )}
                Scan watchlist
              </Button>
            </div>
          </div>
        </div>

        {summary && (
          <Card className="border-border/80 shadow-none">
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-base">
                <BarChart3 className="size-4" />
                Latest scan report
              </CardTitle>
              <CardDescription>
                Source: {summary.source_path || "No persisted scan yet"}
              </CardDescription>
            </CardHeader>
            <CardContent className="grid gap-4">
              <div className="grid gap-3 md:grid-cols-4">
                <div className="rounded-xl border bg-background/60 p-3">
                  <div className="text-muted-foreground text-xs">Scanned</div>
                  <div className="font-semibold text-2xl">{summary.scanned}</div>
                </div>
                <div className="rounded-xl border bg-background/60 p-3">
                  <div className="text-muted-foreground text-xs">Candidates</div>
                  <div className="font-semibold text-2xl">
                    {summary.candidate_count}
                  </div>
                </div>
                <div className="rounded-xl border bg-background/60 p-3">
                  <div className="text-muted-foreground text-xs">Watch</div>
                  <div className="font-semibold text-2xl">{summary.watch_count}</div>
                </div>
                <div className="rounded-xl border bg-background/60 p-3">
                  <div className="text-muted-foreground text-xs">Risk / Exit</div>
                  <div className="font-semibold text-2xl">
                    {summary.risk_count + summary.exit_count}
                  </div>
                </div>
              </div>
              <ul className="grid gap-2 text-muted-foreground text-sm leading-6">
                {summary.report_lines.map((line) => (
                  <li key={line}>• {line}</li>
                ))}
              </ul>
            </CardContent>
          </Card>
        )}

        {scanMutation.error && (
          <Alert variant="destructive">
            <AlertTriangle className="size-4" />
            <AlertTitle>Scan failed</AlertTitle>
            <AlertDescription>{scanMutation.error.message}</AlertDescription>
          </Alert>
        )}

        {scanMutation.isPending && <ScanSkeleton />}

        {result && (
          <>
            <div className="grid gap-3 md:grid-cols-4">
              <Card className="shadow-none">
                <CardHeader className="pb-2">
                  <CardDescription>This scan</CardDescription>
                  <CardTitle>{result.scanned}</CardTitle>
                </CardHeader>
              </Card>
              <Card className="shadow-none">
                <CardHeader className="pb-2">
                  <CardDescription>Candidate</CardDescription>
                  <CardTitle>{groups.candidate.length}</CardTitle>
                </CardHeader>
              </Card>
              <Card className="shadow-none">
                <CardHeader className="pb-2">
                  <CardDescription>Risk</CardDescription>
                  <CardTitle>{groups.risk.length + groups.exit.length}</CardTitle>
                </CardHeader>
              </Card>
              <Card className="shadow-none">
                <CardHeader className="pb-2">
                  <CardDescription>Persisted</CardDescription>
                  <CardTitle className="text-base">
                    {result.persisted_path ? "Yes" : "No"}
                  </CardTitle>
                </CardHeader>
              </Card>
            </div>

            {result.persisted_path && (
              <Alert>
                <Archive className="size-4" />
                <AlertTitle>Persisted local analysis memory</AlertTitle>
                <AlertDescription className="break-all">
                  {result.persisted_path}
                </AlertDescription>
              </Alert>
            )}

            <div className="grid gap-5">
              {groups.candidate.length > 0 && (
                <section className="grid gap-3">
                  <div className="flex items-center gap-2 font-semibold">
                    <CheckCircle2 className="size-4 text-emerald-500" />
                    Candidates
                  </div>
                  {groups.candidate.map((item) => (
                    <ScanItemCard item={item} key={item.ticker} />
                  ))}
                </section>
              )}

              {groups.watch.length > 0 && (
                <section className="grid gap-3">
                  <div className="flex items-center gap-2 font-semibold">
                    <BarChart3 className="size-4" />
                    Watch
                  </div>
                  {groups.watch.map((item) => (
                    <ScanItemCard item={item} key={item.ticker} />
                  ))}
                </section>
              )}

              {(groups.risk.length > 0 || groups.exit.length > 0) && (
                <section className="grid gap-3">
                  <div className="flex items-center gap-2 font-semibold">
                    <ShieldAlert className="size-4 text-amber-500" />
                    Risk and exit
                  </div>
                  {[...groups.risk, ...groups.exit].map((item) => (
                    <ScanItemCard item={item} key={item.ticker} />
                  ))}
                </section>
              )}
            </div>
          </>
        )}
      </section>
    </div>
  );
}
