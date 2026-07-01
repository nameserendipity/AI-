import {
  Activity,
  AlertTriangle,
  BarChart3,
  ChevronDown,
  ChevronUp,
  Landmark,
  Loader2,
  Minus,
  Plus,
  RefreshCw,
  ShieldCheck,
  Trash2,
  TrendingDown,
  TrendingUp,
} from "lucide-react";
import { useState } from "react";
import {
  useAnalyzeFund,
  useCreateFund,
  useDeleteFund,
  useListFunds,
  type FundAnalysisData,
  type FundData,
  type HoldingAnalysisData,
} from "@/api/fund";
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
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { cn } from "@/lib/utils";

// ─── helpers ───────────────────────────────────────────────────────────

const biasCopy: Record<string, string> = {
  bullish: "看涨",
  bearish: "看跌",
  neutral: "中性",
  mixed: "分歧",
  unknown: "未知",
};

const biasClass: Record<string, string> = {
  bullish:
    "border-emerald-500/30 bg-emerald-500/10 text-emerald-600 dark:text-emerald-300",
  bearish:
    "border-rose-500/30 bg-rose-500/10 text-rose-600 dark:text-rose-300",
  neutral: "border-border bg-secondary text-secondary-foreground",
  mixed:
    "border-amber-500/30 bg-amber-500/10 text-amber-600 dark:text-amber-300",
  unknown: "border-border bg-muted text-muted-foreground",
};

const scoreColor = (score: number) => {
  if (score >= 60) return "text-emerald-500";
  if (score >= 30) return "text-amber-500";
  if (score >= 0) return "text-orange-500";
  return "text-rose-500";
};

const scoreBg = (score: number) => {
  if (score >= 60) return "bg-emerald-500";
  if (score >= 30) return "bg-amber-500";
  if (score >= 0) return "bg-orange-500";
  return "bg-rose-500";
};

function BiasBadge({ bias }: { bias: string }) {
  return (
    <Badge variant="outline" className={cn("font-medium", biasClass[bias])}>
      {biasCopy[bias] ?? bias}
    </Badge>
  );
}

function ScoreGauge({ score }: { score: number }) {
  const pct = Math.max(0, Math.min(100, score));
  return (
    <div className="flex items-center gap-3">
      <span className={cn("text-3xl font-bold tabular-nums", scoreColor(score))}>
        {score.toFixed(0)}
      </span>
      <div className="flex-1 h-2.5 rounded-full bg-secondary overflow-hidden">
        <div
          className={cn("h-full rounded-full transition-all", scoreBg(score))}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}

function formatPct(v: number | undefined | null) {
  if (v == null) return "--";
  return `${v.toFixed(2)}%`;
}

// ─── Holding Row ────────────────────────────────────────────────────────

function HoldingRow({
  h,
  defaultOpen,
}: {
  h: HoldingAnalysisData;
  defaultOpen?: boolean;
}) {
  const [open, setOpen] = useState(defaultOpen ?? false);
  return (
    <>
      <TableRow
        className="cursor-pointer"
        onClick={() => setOpen(!open)}
      >
        <TableCell className="font-medium">
          {h.name ?? h.ticker}
          {h.company_name && (
            <span className="ml-1.5 text-muted-foreground text-xs">
              {h.company_name}
            </span>
          )}
        </TableCell>
        <TableCell>{formatPct(h.weight)}</TableCell>
        <TableCell>
          <BiasBadge bias={h.technical_trend} />
        </TableCell>
        <TableCell>
          <BiasBadge bias={h.sentiment_bias} />
        </TableCell>
        <TableCell>
          <BiasBadge bias={h.bias} />
        </TableCell>
        <TableCell>
          <span className="tabular-nums">
            {h.confidence > 0 ? `${(h.confidence * 100).toFixed(0)}%` : "--"}
          </span>
        </TableCell>
        <TableCell>
          <span
            className={cn(
              "tabular-nums font-semibold",
              h.score > 0 ? "text-emerald-500" : h.score < 0 ? "text-rose-500" : "",
            )}
          >
            {h.error ? "—" : h.score.toFixed(1)}
          </span>
        </TableCell>
        <TableCell>
          {open ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
        </TableCell>
      </TableRow>
      {open && (
        <TableRow>
          <TableCell colSpan={8} className="bg-muted/30 pb-4 pt-2">
            {h.error ? (
              <p className="text-rose-500 text-sm">分析失败：{h.error}</p>
            ) : (
              <div className="space-y-2 text-sm">
                {h.summary && (
                  <p className="text-muted-foreground">{h.summary}</p>
                )}
                {h.key_points.length > 0 && (
                  <div>
                    <span className="font-medium text-xs">关键点：</span>
                    <ul className="ml-4 list-disc text-muted-foreground">
                      {h.key_points.map((p, i) => (
                        <li key={i}>{p}</li>
                      ))}
                    </ul>
                  </div>
                )}
                {h.risk_flags.length > 0 && (
                  <div>
                    <span className="font-medium text-xs text-rose-500">
                      风险提示：
                    </span>
                    <ul className="ml-4 list-disc text-rose-400">
                      {h.risk_flags.map((p, i) => (
                        <li key={i}>{p}</li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            )}
          </TableCell>
        </TableRow>
      )}
    </>
  );
}

// ─── Fund Card ──────────────────────────────────────────────────────────

function FundCard({
  fund,
  selected,
  onSelect,
}: {
  fund: FundData;
  selected: boolean;
  onSelect: () => void;
}) {
  return (
    <Card
      className={cn(
        "cursor-pointer transition-all hover:border-primary/50",
        selected && "border-primary ring-1 ring-primary",
      )}
      onClick={onSelect}
    >
      <CardHeader className="p-4 pb-2">
        <CardTitle className="flex items-center gap-2 text-base">
          <Landmark size={16} />
          {fund.name}
        </CardTitle>
        {fund.code && (
          <CardDescription>{fund.code}</CardDescription>
        )}
      </CardHeader>
      <CardContent className="p-4 pt-2">
        <p className="text-muted-foreground text-xs">
          {fund.holdings_count} 只持仓
        </p>
      </CardContent>
    </Card>
  );
}

// ─── Create Fund Form ───────────────────────────────────────────────────

function CreateFundForm({
  onCreated,
}: {
  onCreated: (fund: FundData) => void;
}) {
  const [name, setName] = useState("");
  const [code, setCode] = useState("");
  const create = useCreateFund();

  const handleSubmit = async () => {
    if (!name.trim()) return;
    const res = await create.mutateAsync({
      name: name.trim(),
      code: code.trim() || undefined,
    });
    // res is ApiResponse<FundData>
    onCreated(res.data as unknown as FundData);
    setName("");
    setCode("");
  };

  return (
    <Card>
      <CardHeader className="p-4 pb-2">
        <CardTitle className="text-sm">添加基金</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3 p-4 pt-2">
        <div className="space-y-1">
          <Label className="text-xs">基金名称</Label>
          <Input
            placeholder="如：东方人工智能混合C"
            value={name}
            onChange={(e) => setName(e.target.value)}
          />
        </div>
        <div className="space-y-1">
          <Label className="text-xs">基金代码（可选）</Label>
          <Input
            placeholder="如：014811"
            value={code}
            onChange={(e) => setCode(e.target.value)}
          />
        </div>
        <Button
          size="sm"
          className="w-full"
          onClick={handleSubmit}
          disabled={!name.trim() || create.isPending}
        >
          {create.isPending ? (
            <Loader2 className="mr-1 h-4 w-4 animate-spin" />
          ) : (
            <Plus className="mr-1 h-4 w-4" />
          )}
          添加
        </Button>
      </CardContent>
    </Card>
  );
}

// ─── Analysis View ──────────────────────────────────────────────────────

function AnalysisView({ analysis }: { analysis: FundAnalysisData }) {
  const bias = analysis.overall_bias;
  const suggestionIcon = () => {
    if (analysis.total_score >= 60) return <TrendingUp className="h-5 w-5" />;
    if (analysis.total_score >= 30)
      return <Activity className="h-5 w-5" />;
    if (analysis.total_score >= 0) return <Minus className="h-5 w-5" />;
    return <TrendingDown className="h-5 w-5" />;
  };

  return (
    <div className="space-y-6">
      {/* Score overview */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardHeader className="p-4 pb-2">
            <CardTitle className="text-xs text-muted-foreground">
              综合评分
            </CardTitle>
          </CardHeader>
          <CardContent className="p-4 pt-0">
            <ScoreGauge score={analysis.total_score} />
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="p-4 pb-2">
            <CardTitle className="text-xs text-muted-foreground">
              综合倾向
            </CardTitle>
          </CardHeader>
          <CardContent className="p-4 pt-0">
            <BiasBadge bias={bias} />
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="p-4 pb-2">
            <CardTitle className="text-xs text-muted-foreground">
              平均置信度
            </CardTitle>
          </CardHeader>
          <CardContent className="p-4 pt-0">
            <span className="text-2xl font-bold tabular-nums">
              {(analysis.weighted_confidence * 100).toFixed(0)}%
            </span>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="p-4 pb-2">
            <CardTitle className="text-xs text-muted-foreground">
              分析覆盖
            </CardTitle>
          </CardHeader>
          <CardContent className="p-4 pt-0">
            <span className="text-2xl font-bold tabular-nums">
              {analysis.holdings_analyzed}/{analysis.holdings_total}
            </span>
          </CardContent>
        </Card>
      </div>

      {/* Suggestion */}
      <Alert
        className={cn(
          "border-l-4",
          analysis.total_score >= 60
            ? "border-l-emerald-500"
            : analysis.total_score >= 30
              ? "border-l-amber-500"
              : analysis.total_score >= 0
                ? "border-l-orange-500"
                : "border-l-rose-500",
        )}
      >
        <div className="flex items-center gap-2">
          {suggestionIcon()}
          <AlertTitle className="mb-0">建议</AlertTitle>
        </div>
        <AlertDescription className="mt-2">
          {analysis.suggestion}
        </AlertDescription>
      </Alert>

      {/* Holdings table */}
      <Card>
        <CardHeader className="p-4 pb-2">
          <CardTitle className="text-sm">持仓股分析明细</CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>股票</TableHead>
                <TableHead>权重</TableHead>
                <TableHead>技术面</TableHead>
                <TableHead>消息面</TableHead>
                <TableHead>综合</TableHead>
                <TableHead>置信度</TableHead>
                <TableHead>评分</TableHead>
                <TableHead></TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {analysis.holding_results.map((h) => (
                <HoldingRow key={h.ticker} h={h} />
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      {/* Aggregated insights */}
      {analysis.aggregated_key_points.length > 0 && (
        <Card>
          <CardHeader className="p-4 pb-2">
            <CardTitle className="flex items-center gap-1.5 text-sm">
              <Activity size={15} />
              综合要点
            </CardTitle>
          </CardHeader>
          <CardContent className="p-4 pt-2">
            <ul className="ml-4 list-disc space-y-1 text-sm text-muted-foreground">
              {analysis.aggregated_key_points.map((p, i) => (
                <li key={i}>{p}</li>
              ))}
            </ul>
          </CardContent>
        </Card>
      )}

      {analysis.aggregated_risk_flags.length > 0 && (
        <Card>
          <CardHeader className="p-4 pb-2">
            <CardTitle className="flex items-center gap-1.5 text-sm text-rose-500">
              <AlertTriangle size={15} />
              综合风险
            </CardTitle>
          </CardHeader>
          <CardContent className="p-4 pt-2">
            <ul className="ml-4 list-disc space-y-1 text-sm text-rose-400">
              {analysis.aggregated_risk_flags.map((p, i) => (
                <li key={i}>{p}</li>
              ))}
            </ul>
          </CardContent>
        </Card>
      )}

      {/* Timestamp */}
      <p className="text-right text-xs text-muted-foreground">
        分析时间：{analysis.analyzed_at}
      </p>
    </div>
  );
}

// ─── Main Page ──────────────────────────────────────────────────────────

export default function FundDashboard() {
  const { data: funds, isLoading: fundsLoading } = useListFunds();
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const selectedFund = funds?.find((f) => f.id === selectedId) ?? null;

  const {
    data: analysis,
    isLoading: analysisLoading,
    isError: analysisError,
    refetch: refetchAnalysis,
    isRefetching: isRefetchingAnalysis,
  } = useAnalyzeFund(selectedId);

  const deleteFund = useDeleteFund();
  const createFund = useCreateFund();

  const handleDelete = async (id: number) => {
    await deleteFund.mutateAsync(id);
    if (selectedId === id) setSelectedId(null);
  };

  return (
    <div className="flex h-full gap-4 p-4">
      {/* Left sidebar — fund list */}
      <div className="flex w-72 shrink-0 flex-col gap-3 overflow-y-auto">
        <div className="flex items-center justify-between">
          <h2 className="flex items-center gap-1.5 font-semibold text-lg">
            <Landmark size={18} />
            我的基金
          </h2>
        </div>

        {fundsLoading ? (
          <div className="space-y-2">
            <Skeleton className="h-24 w-full" />
            <Skeleton className="h-24 w-full" />
          </div>
        ) : (
          <div className="space-y-2">
            {funds?.length === 0 && (
              <p className="py-4 text-center text-sm text-muted-foreground">
                还没有添加基金
              </p>
            )}
            {funds?.map((f) => (
              <div key={f.id} className="relative group">
                <FundCard
                  fund={f}
                  selected={f.id === selectedId}
                  onSelect={() => setSelectedId(f.id)}
                />
                <button
                  className="absolute top-2 right-2 hidden rounded p-1 text-muted-foreground hover:bg-destructive/10 hover:text-destructive group-hover:block"
                  onClick={(e) => {
                    e.stopPropagation();
                    handleDelete(f.id);
                  }}
                  title="删除基金"
                >
                  <Trash2 size={14} />
                </button>
              </div>
            ))}
          </div>
        )}

        <CreateFundForm
          onCreated={(fund) => {
            setSelectedId(fund.id);
          }}
        />
      </div>

      {/* Right — analysis content */}
      <div className="flex-1 overflow-y-auto">
        {!selectedFund ? (
          <div className="flex h-full items-center justify-center text-muted-foreground">
            <p>请从左侧选择一个基金查看分析</p>
          </div>
        ) : analysisLoading ? (
          <div className="space-y-4">
            <Skeleton className="h-32 w-full" />
            <Skeleton className="h-64 w-full" />
          </div>
        ) : analysisError ? (
          <Alert variant="destructive">
            <AlertTriangle className="h-4 w-4" />
            <AlertTitle>分析失败</AlertTitle>
            <AlertDescription>
              无法完成基金分析。请确认后端已启动且 A-share 数据服务可用。
              <div className="mt-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => refetchAnalysis()}
                  disabled={isRefetchingAnalysis}
                >
                  <RefreshCw
                    className={cn(
                      "mr-1 h-3 w-3",
                      isRefetchingAnalysis && "animate-spin",
                    )}
                  />
                  重试
                </Button>
              </div>
            </AlertDescription>
          </Alert>
        ) : analysis ? (
          <AnalysisView analysis={analysis} />
        ) : (
          <div className="flex h-full items-center justify-center text-muted-foreground">
            <p>点击「分析」查看结果</p>
          </div>
        )}
      </div>
    </div>
  );
}
