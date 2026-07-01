import { X } from "lucide-react";
import { Link, type LinkProps } from "react-router";
import { cn, formatChange, getChangeType } from "@/lib/utils";
import { useStockColors } from "@/store/settings-store";

interface Stock {
  symbol: string;
  companyName: string;
  price: string;
  changePercent?: number;
  icon?: string;
  iconBgColor?: string;
}

export interface StockGroup {
  title: string;
  stocks: Stock[];
}

interface StockMenuProps extends React.HTMLAttributes<HTMLDivElement> {
  children: React.ReactNode;
}

interface StockMenuHeaderProps
  extends React.HTMLAttributes<HTMLHeadingElement> {
  children: React.ReactNode;
}

interface StockMenuGroupProps extends React.HTMLAttributes<HTMLDivElement> {
  children: React.ReactNode;
}

interface StockMenuGroupHeaderProps
  extends React.HTMLAttributes<HTMLDivElement> {
  children: React.ReactNode;
}

interface StockMenuListItemProps extends LinkProps {
  stock: Stock;
  isActive?: boolean;
  onRemove?: React.MouseEventHandler<HTMLButtonElement>;
  isRemoving?: boolean;
}

function StockMenuHeader({
  className,
  children,
  ...props
}: StockMenuHeaderProps) {
  return (
    <h1 className={cn("px-2 font-semibold text-lg", className)} {...props}>
      {children}
    </h1>
  );
}

function StockMenu({ className, children, ...props }: StockMenuProps) {
  return (
    <div
      className={cn("flex min-h-20 flex-1 flex-col gap-6 px-5 py-6", className)}
      {...props}
    >
      {children}
    </div>
  );
}

function StockMenuGroup({
  className,
  children,
  ...props
}: StockMenuGroupProps) {
  return (
    <div
      className={cn("not-last:mb-6 flex flex-col gap-2", className)}
      {...props}
    >
      {children}
    </div>
  );
}

function StockMenuGroupHeader({
  className,
  children,
  ...props
}: StockMenuGroupHeaderProps) {
  return (
    <div className={cn("px-2 font-normal text-base", className)} {...props}>
      {children}
    </div>
  );
}

function StockMenuListItem({
  className,
  stock,
  onClick,
  isActive,
  onRemove,
  isRemoving,
  ...props
}: StockMenuListItemProps) {
  const stockColors = useStockColors();
  const changeType = getChangeType(stock.changePercent);

  return (
    <Link
      className={cn(
        "group flex items-center justify-between gap-4 rounded-lg p-2",
        "cursor-pointer transition-colors hover:bg-accent/80",
        className,
        { "bg-accent/80": isActive },
      )}
      {...props}
    >
      <div className="flex flex-1 items-center gap-2.5 truncate">
        {/* stock info */}
        <div className="flex flex-col items-start gap-1">
          <p className="font-semibold text-foreground text-sm leading-tight">
            {stock.symbol}
          </p>
          <p className="text-muted-foreground/80 text-xs leading-none">
            {stock.companyName}
          </p>
        </div>
      </div>

      {/* price info */}
      <div className="flex items-center gap-1.5">
        <div className="flex flex-col items-end gap-1">
          <p className="font-semibold text-sm">{stock.price}</p>
          <p
            className="font-semibold text-xs leading-relaxed"
            style={{
              color: stockColors[changeType],
            }}
          >
            {formatChange(stock.changePercent, "%")}
          </p>
        </div>
        {onRemove && (
          <button
            type="button"
            aria-label={`Remove ${stock.symbol}`}
            className="rounded-md p-1 text-muted-foreground opacity-0 transition hover:bg-destructive/10 hover:text-destructive group-hover:opacity-100 focus:opacity-100"
            disabled={isRemoving}
            onClick={(event) => {
              event.preventDefault();
              event.stopPropagation();
              onRemove(event);
            }}
          >
            <X className="size-3.5" />
          </button>
        )}
      </div>
    </Link>
  );
}

export {
  StockMenu,
  StockMenuHeader,
  StockMenuGroup,
  StockMenuGroupHeader,
  StockMenuListItem,
};
