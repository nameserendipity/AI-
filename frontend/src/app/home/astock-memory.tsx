import {
  AlertCircle,
  BrainCircuit,
  Clock3,
  ExternalLink,
  Loader2,
  RefreshCw,
  TrendingDown,
  TrendingUp,
} from "lucide-react";
import { Link } from "react-router";
import { useAStockMemoryLatest } from "@/api/astock";
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
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";
import type { AStockMemoryItem } from "@/types/astock";

const trendCopy: Record<string, string> = {
  bullish: "看涨",
  bearish: "看跌",
  neutral: "中性",
  mixed: "分歧",
  unknown: "未知",
};

const memoryDeltaCopy: Record<string, string> = {
  improved: "转强",
  weakened: "转弱",
  continued: "延续",
  reversed: "反转",
  new: "新增",
};

function formatNumber(value?: number | null, digits = 2) {
  if (value === null || value === undefined || Number.isNaN(value)) return "--";
  return value.toFixed(digits);
}

function formatPercent(value?: number | null) {
  if (value === null || value === undefined || Number.isNaN(value)) return "--";
  return `${value.toFixed(2)}%`;
}

function formatDateTime(value?: string | null) {
  if (!value) return "--";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString("zh-CN", { hour12: false });
}

function trendClass(trend?: string | null) {
  if (trend === "bullish") {
    return "border-emerald-500/30 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300";
  }
  if (trend === "bearish") {
    return "border-rose-500/30 bg-rose-500/10 text-rose-700 dark:text-rose-300";
  }
  if (trend === "mixed") {
    return "border-amber-500/30 bg-amber-500/10 text-amber-700 dark:text-amber-300";
  }
  return "border-border bg-secondary text-secondary-foreground";
}

function MemoryMetric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border bg-background/60 p-3">
      <div className="text-muted-foreground text-xs">{label}</div>
      <div className="mt-1 font-semibold text-lg">{value}</div>
    </div>
  );
}

function MemoryItemCard({ item }: { item: AStockMemoryItem }) {
  const title = item.display_name || item.normalized_symbol || item.ticker;
  const trend = item.trend || "unknown";
  const symbol = item.normalized_symbol || item.ticker;
  const isAnalyzed = item.status === "analyzed";

  return (
    <Card className="overflow-hidden border-border/80 shadow-none">
      <CardHeader className="border-b bg-muted/25">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
          <div className="min-w-0">
            <div className="mb-2 flex flex-wrap items-center gap-2">
              <Badge className={cn("border", trendClass(trend))}>
                {trendCopy[trend] || trend}
              </Badge>
              {item.memory_delta ? (
                <Badge variant="secondary">
                  记忆{memoryDeltaCopy[item.memory_delta] || item.memory_delta}
                </Badge>
              ) : null}
              <Badge variant={isAnalyzed ? "outline" : "secondary"}>
                {isAnalyzed ? "已分析" : item.status}
              </Badge>
            </div>
            <CardTitle className="text-xl">{title}</CardTitle>
            <CardDescription className="mt-1">
              {symbol} · {item.horizon || "未来几日/短线"}
            </CardDescription>
          </div>

          <div className="flex items-center gap-2">
            {trend === "bearish" ? (
              <TrendingDown className="size-5 text-rose-500" />
            ) : (
              <TrendingUp className="size-5 text-emerald-500" />
            )}
            <div className="text-right">
              <div className="text-muted-foreground text-xs">置信度</div>
              <div className="font-semibold text-2xl">
                {item.confidence === null || item.confidence === undefined
                  ? "--"
                  : `${Math.round(item.confidence * 100)}%`}
              </div>
            </div>
          </div>
        </div>
      </CardHeader>

      <CardContent className="grid gap-4 p-4">
        <div className="grid gap-3 md:grid-cols-4">
          <MemoryMetric label="最新价" value={formatNumber(item.latest_price)} />
          <MemoryMetric label="5日涨跌" value={formatPercent(item.change_5d_pct)} />
          <MemoryMetric label="20日涨跌" value={formatPercent(item.change_20d_pct)} />
          <MemoryMetric label="策略动作" value={item.action || "hold"} />
        </div>

        {item.reason ? (
          <div className="rounded-xl border bg-background/60 p-4">
            <div className="mb-2 font-medium text-sm">DeepSeek 分析理由</div>
            <p className="whitespace-pre-wrap text-muted-foreground text-sm leading-6">
              {item.reason}
            </p>
          </div>
        ) : null}

        {!isAnalyzed && (item.skip_reason || item.error_message) ? (
          <Alert variant={item.error_message ? "destructive" : "default"}>
            <AlertCircle className="size-4" />
            <AlertTitle>{item.error_message ? "分析失败" : "已跳过"}</AlertTitle>
            <AlertDescription>
              {item.error_message || item.skip_reason}
            </AlertDescription>
          </Alert>
        ) : null}

        <div className="grid gap-3 md:grid-cols-2">
          <div className="rounded-xl border bg-background/60 p-4">
            <div className="mb-3 font-medium text-sm">关键依据</div>
            {item.key_points.length > 0 ? (
              <ul className="grid gap-2 text-muted-foreground text-sm leading-6">
                {item.key_points.slice(0, 5).map((point) => (
                  <li key={point}>• {point}</li>
                ))}
              </ul>
            ) : (
              <p className="text-muted-foreground text-sm">暂无关键依据。</p>
            )}
          </div>

          <div className="rounded-xl border bg-background/60 p-4">
            <div className="mb-3 font-medium text-sm">风险点</div>
            {item.risk_flags.length > 0 || item.blocked_reasons.length > 0 ? (
              <ul className="grid gap-2 text-muted-foreground text-sm leading-6">
                {[...item.risk_flags, ...item.blocked_reasons]
                  .slice(0, 5)
                  .map((risk) => (
                    <li key={risk}>• {risk}</li>
                  ))}
              </ul>
            ) : (
              <p className="text-muted-foreground text-sm">暂无明显风险点。</p>
            )}
          </div>
        </div>

        {item.normalized_symbol ? (
          <div className="flex justify-end">
            <Button asChild size="sm" variant="secondary">
              <Link
                to={`/home/astock-preview?symbol=${encodeURIComponent(
                  item.normalized_symbol,
                )}`}
              >
                打开单票预检
                <ExternalLink className="size-4" />
              </Link>
            </Button>
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
}

function MemorySkeleton() {
  return (
    <div className="grid gap-4">
      <Skeleton className="h-48 rounded-xl" />
      <Skeleton className="h-64 rounded-xl" />
      <Skeleton className="h-64 rounded-xl" />
    </div>
  );
}

export default function AStockMemoryPage() {
  const latestQuery = useAStockMemoryLatest();
  const run = latestQuery.data?.run ?? null;
  const items = latestQuery.data?.items ?? [];
  const analyzedItems = items.filter((item) => item.status === "analyzed");
  const skippedItems = items.filter((item) => item.status !== "analyzed");

  return (
    <div className="scroll-container h-full bg-card px-6 py-6">
      <section className="mx-auto flex max-w-6xl flex-col gap-6">
        <div className="rounded-2xl border bg-gradient-to-br from-background via-background to-muted/60 p-6 shadow-sm">
          <div className="flex flex-col gap-5 lg:flex-row lg:items-start lg:justify-between">
            <div className="max-w-3xl">
              <div className="mb-3 inline-flex items-center gap-2 rounded-full border bg-background px-3 py-1 text-muted-foreground text-xs">
                <BrainCircuit className="size-3.5" />
                DeepSeek 股票分析记忆
              </div>
              <h1 className="font-semibold text-3xl tracking-tight">
                每支自选股的模型判断都写在这里
              </h1>
              <p className="mt-3 text-muted-foreground text-sm leading-6">
                这里读取定时脚本写入本地数据库的最新结果，展示 DeepSeek 对每支股票的趋势判断、理由、风险点和历史记忆变化。
              </p>
            </div>

            <Button
              disabled={latestQuery.isFetching}
              onClick={() => latestQuery.refetch()}
              variant="secondary"
            >
              {latestQuery.isFetching ? (
                <Loader2 className="size-4 animate-spin" />
              ) : (
                <RefreshCw className="size-4" />
              )}
              刷新
            </Button>
          </div>
        </div>

        {latestQuery.isLoading && <MemorySkeleton />}

        {latestQuery.isError && (
          <Alert variant="destructive">
            <AlertCircle className="size-4" />
            <AlertTitle>读取失败</AlertTitle>
            <AlertDescription>
              {latestQuery.error instanceof Error
                ? latestQuery.error.message
                : "请确认后端已启动。"}
            </AlertDescription>
          </Alert>
        )}

        {!latestQuery.isLoading && !latestQuery.isError && !run && (
          <Alert>
            <AlertCircle className="size-4" />
            <AlertTitle>还没有分析记忆</AlertTitle>
            <AlertDescription>
              请先运行 .\Start-AStock-Memory-Runner.ps1 -Once，或者启动定时脚本后再刷新本页。
            </AlertDescription>
          </Alert>
        )}

        {run && (
          <>
            <Card className="border-border/80 shadow-none">
              <CardHeader>
                <div className="flex flex-col gap-2 lg:flex-row lg:items-start lg:justify-between">
                  <div>
                    <CardTitle className="flex items-center gap-2 text-base">
                      <Clock3 className="size-4" />
                      最新运行概览
                    </CardTitle>
                    <CardDescription>
                      {run.model_provider || "unknown"} / {run.model_id || "unknown"} · 完成时间 {formatDateTime(run.completed_at)}
                    </CardDescription>
                  </div>
                  <Badge variant="secondary">{run.status}</Badge>
                </div>
              </CardHeader>
              <CardContent className="grid gap-4">
                <div className="grid gap-3 md:grid-cols-5">
                  <MemoryMetric label="总数" value={String(run.total_items)} />
                  <MemoryMetric label="已分析" value={String(run.analyzed_items)} />
                  <MemoryMetric label="跳过" value={String(run.skipped_items)} />
                  <MemoryMetric label="错误" value={String(run.error_items)} />
                  <MemoryMetric label="风险" value={run.overall_risk_level || "--"} />
                </div>

                {run.market_summary ? (
                  <div className="rounded-xl border bg-background/60 p-4">
                    <div className="mb-2 font-medium text-sm">DeepSeek 市场总评</div>
                    <p className="whitespace-pre-wrap text-muted-foreground text-sm leading-6">
                      {run.market_summary}
                    </p>
                  </div>
                ) : null}
              </CardContent>
            </Card>

            <div className="grid gap-4">
              {analyzedItems.map((item) => (
                <MemoryItemCard item={item} key={item.id} />
              ))}
            </div>

            {skippedItems.length > 0 && (
              <Card className="border-border/80 shadow-none">
                <CardHeader>
                  <CardTitle className="text-base">未纳入本次 A股分析的标的</CardTitle>
                  <CardDescription>
                    这些标的通常是美股、港股、指数或暂不支持的格式。
                  </CardDescription>
                </CardHeader>
                <CardContent className="grid gap-2">
                  {skippedItems.map((item) => (
                    <div
                      className="flex flex-col gap-1 rounded-lg border bg-muted/25 px-3 py-2 text-sm md:flex-row md:items-center md:justify-between"
                      key={item.id}
                    >
                      <span className="font-medium">{item.display_name || item.ticker}</span>
                      <span className="text-muted-foreground">
                        {item.skip_reason || item.error_message || item.status}
                      </span>
                    </div>
                  ))}
                </CardContent>
              </Card>
            )}
          </>
        )}
      </section>
    </div>
  );
}
