import {
  Activity,
  AlertTriangle,
  BarChart3,
  CheckCircle2,
  Loader2,
  ShieldCheck,
  TrendingDown,
  TrendingUp,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router";
import { useAStockStrategyPreview } from "@/api/astock";
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
import type { AStockBias, AStockPreviewAction } from "@/types/astock";

const actionCopy: Record<AStockPreviewAction, string> = {
  buy: "买入",
  sell: "卖出",
  hold: "观望",
};

const biasCopy: Record<AStockBias, string> = {
  bullish: "偏多",
  bearish: "偏空",
  neutral: "中性",
  mixed: "分歧",
  unknown: "未知",
};

const biasClass: Record<AStockBias, string> = {
  bullish: "border-emerald-500/30 bg-emerald-500/10 text-emerald-600 dark:text-emerald-300",
  bearish: "border-rose-500/30 bg-rose-500/10 text-rose-600 dark:text-rose-300",
  neutral: "border-border bg-secondary text-secondary-foreground",
  mixed: "border-amber-500/30 bg-amber-500/10 text-amber-600 dark:text-amber-300",
  unknown: "border-border bg-muted text-muted-foreground",
};

const actionClass: Record<AStockPreviewAction, string> = {
  buy: "bg-emerald-500 text-white",
  sell: "bg-rose-500 text-white",
  hold: "bg-zinc-900 text-white dark:bg-zinc-100 dark:text-zinc-950",
};

function formatNumber(value?: number | null, digits = 2) {
  if (value === null || value === undefined || Number.isNaN(value)) return "--";
  return value.toFixed(digits);
}

function formatPercent(value?: number | null) {
  if (value === null || value === undefined || Number.isNaN(value)) return "--";
  return `${value.toFixed(2)}%`;
}

function MetricTile({
  label,
  value,
  tone = "default",
}: {
  label: string;
  value: string;
  tone?: "default" | "positive" | "negative" | "warning";
}) {
  return (
    <div
      className={cn(
        "rounded-xl border bg-background/60 p-4",
        tone === "positive" && "border-emerald-500/20 bg-emerald-500/5",
        tone === "negative" && "border-rose-500/20 bg-rose-500/5",
        tone === "warning" && "border-amber-500/20 bg-amber-500/5",
      )}
    >
      <div className="text-muted-foreground text-xs">{label}</div>
      <div className="mt-2 font-semibold text-2xl tracking-tight">{value}</div>
    </div>
  );
}

function LoadingPreview() {
  return (
    <div className="grid gap-4 lg:grid-cols-[1.1fr_0.9fr]">
      <Skeleton className="h-72 rounded-xl" />
      <Skeleton className="h-72 rounded-xl" />
      <Skeleton className="h-48 rounded-xl lg:col-span-2" />
    </div>
  );
}

export default function AStockPreviewPage() {
  const [searchParams] = useSearchParams();
  const urlSymbol = searchParams.get("symbol") ?? "300750";
  const [symbol, setSymbol] = useState(urlSymbol);

  useEffect(() => {
    setSymbol(urlSymbol);
  }, [urlSymbol]);
  const [initialCapital, setInitialCapital] = useState(100000);
  const [currentPositionQty, setCurrentPositionQty] = useState(0);
  const [maxPositionPct, setMaxPositionPct] = useState(0.3);
  const [openPositionPct, setOpenPositionPct] = useState(0.1);
  const previewMutation = useAStockStrategyPreview();

  const result = previewMutation.data;
  const technical = result?.analysis.technical;
  const sentiment = result?.analysis.sentiment;

  const technicalTone = useMemo(() => {
    if (!technical) return "default";
    if (technical.trend === "bullish") return "positive";
    if (technical.trend === "bearish") return "negative";
    if (technical.trend === "mixed") return "warning";
    return "default";
  }, [technical]);

  const handleSubmit = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    previewMutation.mutate({
      symbol: symbol.trim(),
      initial_capital: initialCapital,
      current_position_qty: currentPositionQty,
      max_position_pct: maxPositionPct,
      open_position_pct: openPositionPct,
      min_open_confidence: 0.6,
    });
  };

  return (
    <div className="scroll-container h-full bg-card px-6 py-6">
      <section className="mx-auto flex max-w-6xl flex-col gap-6">
        <div className="rounded-2xl border bg-gradient-to-br from-background via-background to-muted/60 p-6 shadow-sm">
          <div className="flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
            <div className="max-w-2xl">
              <div className="mb-3 inline-flex items-center gap-2 rounded-full border bg-background px-3 py-1 text-muted-foreground text-xs">
                <ShieldCheck className="size-3.5" />
                A股策略预检
              </div>
              <h1 className="font-semibold text-3xl tracking-tight">
                先看数据和保护层，再决定是否交易
              </h1>
              <p className="mt-3 text-muted-foreground text-sm leading-6">
                面板会调用本地 A股数据层，生成走势分析，再经过 AStockGuardrails 输出最终 buy、sell 或 hold。默认不下真实订单。
              </p>
            </div>

            <form
              className="grid w-full gap-3 rounded-xl border bg-card p-4 lg:w-[420px]"
              onSubmit={handleSubmit}
            >
              <div className="grid grid-cols-2 gap-3">
                <div className="col-span-2 grid gap-1.5">
                  <Label htmlFor="symbol">股票代码</Label>
                  <Input
                    id="symbol"
                    value={symbol}
                    placeholder="300750"
                    onChange={(event) => setSymbol(event.target.value)}
                  />
                </div>
                <div className="grid gap-1.5">
                  <Label htmlFor="capital">初始资金</Label>
                  <Input
                    id="capital"
                    type="number"
                    value={initialCapital}
                    onChange={(event) =>
                      setInitialCapital(Number(event.target.value || 0))
                    }
                  />
                </div>
                <div className="grid gap-1.5">
                  <Label htmlFor="position">当前持仓</Label>
                  <Input
                    id="position"
                    type="number"
                    value={currentPositionQty}
                    onChange={(event) =>
                      setCurrentPositionQty(Number(event.target.value || 0))
                    }
                  />
                </div>
                <div className="grid gap-1.5">
                  <Label htmlFor="max-position">单票上限</Label>
                  <Input
                    id="max-position"
                    step="0.05"
                    type="number"
                    value={maxPositionPct}
                    onChange={(event) =>
                      setMaxPositionPct(Number(event.target.value || 0))
                    }
                  />
                </div>
                <div className="grid gap-1.5">
                  <Label htmlFor="open-position">试开仓位</Label>
                  <Input
                    id="open-position"
                    step="0.05"
                    type="number"
                    value={openPositionPct}
                    onChange={(event) =>
                      setOpenPositionPct(Number(event.target.value || 0))
                    }
                  />
                </div>
              </div>
              <Button
                className="mt-1 w-full"
                disabled={previewMutation.isPending || !symbol.trim()}
                type="submit"
              >
                {previewMutation.isPending ? (
                  <Loader2 className="size-4 animate-spin" />
                ) : (
                  <Activity className="size-4" />
                )}
                运行预检
              </Button>
            </form>
          </div>
        </div>

        {previewMutation.isPending && <LoadingPreview />}

        {previewMutation.isError && (
          <Alert variant="destructive">
            <AlertTriangle className="size-4" />
            <AlertTitle>预检失败</AlertTitle>
            <AlertDescription>
              {previewMutation.error instanceof Error
                ? previewMutation.error.message
                : "请确认后端服务已启动，并检查股票代码。"}
            </AlertDescription>
          </Alert>
        )}

        {result && !previewMutation.isPending && (
          <div className="grid gap-4 lg:grid-cols-[1.1fr_0.9fr]">
            <Card className="overflow-hidden border-border/80 shadow-none">
              <CardHeader className="border-b bg-muted/30">
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <CardTitle className="text-xl">
                      {result.analysis.name ?? result.symbol}
                    </CardTitle>
                    <CardDescription className="mt-1">
                      {result.symbol} · {result.analysis.exchange}
                    </CardDescription>
                  </div>
                  <Badge className={cn("border", actionClass[result.action])}>
                    {actionCopy[result.action]}
                  </Badge>
                </div>
              </CardHeader>
              <CardContent className="grid gap-5 pt-6">
                <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
                  <MetricTile
                    label="最新价格"
                    value={formatNumber(technical?.latest_close)}
                  />
                  <MetricTile
                    label="综合倾向"
                    value={biasCopy[result.analysis.bias]}
                    tone={
                      result.analysis.bias === "bullish"
                        ? "positive"
                        : result.analysis.bias === "bearish"
                          ? "negative"
                          : result.analysis.bias === "mixed"
                            ? "warning"
                            : "default"
                    }
                  />
                  <MetricTile
                    label="置信度"
                    value={`${Math.round(result.analysis.confidence * 100)}%`}
                  />
                  <MetricTile
                    label="保护后动作"
                    value={actionCopy[result.action]}
                  />
                </div>

                <div className="rounded-xl border bg-background/60 p-4">
                  <div className="mb-2 flex items-center gap-2 font-medium text-sm">
                    <BarChart3 className="size-4" />
                    分析摘要
                  </div>
                  <p className="text-muted-foreground text-sm leading-6">
                    {result.analysis.summary}
                  </p>
                </div>

                <div className="grid gap-3 md:grid-cols-3">
                  <MetricTile
                    label="MA5 / MA20"
                    value={`${formatNumber(technical?.ma5)} / ${formatNumber(technical?.ma20)}`}
                    tone={technicalTone}
                  />
                  <MetricTile
                    label="5日 / 20日涨跌"
                    value={`${formatPercent(technical?.change_5d_pct)} / ${formatPercent(technical?.change_20d_pct)}`}
                    tone={technicalTone}
                  />
                  <MetricTile
                    label="支撑 / 压力"
                    value={`${formatNumber(technical?.support)} / ${formatNumber(technical?.resistance)}`}
                  />
                </div>
              </CardContent>
            </Card>

            <div className="grid gap-4">
              <Card className="border-border/80 shadow-none">
                <CardHeader>
                  <CardTitle className="flex items-center gap-2 text-base">
                    {result.analysis.bias === "bearish" ? (
                      <TrendingDown className="size-4 text-rose-500" />
                    ) : (
                      <TrendingUp className="size-4 text-emerald-500" />
                    )}
                    决策链路
                  </CardTitle>
                  <CardDescription>
                    初始建议 {result.proposed_action}，保护后 {result.action}
                  </CardDescription>
                </CardHeader>
                <CardContent className="grid gap-3">
                  <div className="flex flex-wrap gap-2">
                    <Badge className={cn("border", biasClass[result.analysis.bias])}>
                      综合 {biasCopy[result.analysis.bias]}
                    </Badge>
                    <Badge className={cn("border", biasClass[technical?.trend ?? "unknown"])}>
                      技术 {biasCopy[technical?.trend ?? "unknown"]}
                    </Badge>
                    <Badge className={cn("border", biasClass[sentiment?.bias ?? "unknown"])}>
                      消息 {biasCopy[sentiment?.bias ?? "unknown"]}
                    </Badge>
                  </div>

                  <div className="rounded-xl border bg-muted/30 p-4 text-sm leading-6">
                    {result.rationale}
                  </div>
                </CardContent>
              </Card>

              <Card className="border-border/80 shadow-none">
                <CardHeader>
                  <CardTitle className="flex items-center gap-2 text-base">
                    <ShieldCheck className="size-4" />
                    保护层结果
                  </CardTitle>
                  <CardDescription>
                    做空、杠杆、非交易时间和风险信号会被拦截
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  {result.blocked_reasons.length > 0 ? (
                    <ul className="grid gap-2 text-sm">
                      {result.blocked_reasons.map((reason) => (
                        <li
                          className="rounded-lg border border-amber-500/20 bg-amber-500/5 px-3 py-2 text-amber-700 dark:text-amber-300"
                          key={reason}
                        >
                          {reason}
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <div className="flex items-center gap-2 rounded-lg border border-emerald-500/20 bg-emerald-500/5 px-3 py-2 text-emerald-700 text-sm dark:text-emerald-300">
                      <CheckCircle2 className="size-4" />
                      没有触发阻断规则
                    </div>
                  )}
                </CardContent>
              </Card>
            </div>

            <Card className="border-border/80 shadow-none lg:col-span-2">
              <CardHeader>
                <CardTitle className="text-base">关键依据和风险</CardTitle>
                <CardDescription>
                  这里来自 AStockAnalysisAgent 的结构化分析，不是模型自由发挥
                </CardDescription>
              </CardHeader>
              <CardContent className="grid gap-4 md:grid-cols-2">
                <div className="rounded-xl border bg-background/60 p-4">
                  <div className="mb-3 font-medium text-sm">关键依据</div>
                  <ul className="grid gap-2 text-muted-foreground text-sm leading-6">
                    {result.analysis.key_points.map((point) => (
                      <li key={point}>• {point}</li>
                    ))}
                  </ul>
                </div>
                <div className="rounded-xl border bg-background/60 p-4">
                  <div className="mb-3 font-medium text-sm">风险提示</div>
                  {result.analysis.risk_flags.length > 0 ? (
                    <ul className="grid gap-2 text-muted-foreground text-sm leading-6">
                      {result.analysis.risk_flags.map((risk) => (
                        <li key={risk}>• {risk}</li>
                      ))}
                    </ul>
                  ) : (
                    <p className="text-muted-foreground text-sm">暂无明显风险信号。</p>
                  )}
                </div>
              </CardContent>
            </Card>
          </div>
        )}
      </section>
    </div>
  );
}



