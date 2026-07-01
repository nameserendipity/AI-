import { memo, useMemo } from "react";
import { useTranslation } from "react-i18next";
import { useLocation } from "react-router";
import {
  useGetStockPrice,
  useGetWatchlist,
  useRemoveStockFromWatchlist,
} from "@/api/stock";
import {
  StockMenu,
  StockMenuHeader,
  StockMenuListItem,
} from "@/components/valuecell/menus/stock-menus";
import type { Stock } from "@/types/stock";

function isAStockTicker(ticker: string) {
  return /^(SSE|SZSE|BSE):\d{6}$/i.test(ticker);
}

function getAStockSymbol(ticker: string) {
  return ticker.split(":")[1] ?? ticker;
}

function StockList() {
  const { t } = useTranslation();
  const { pathname } = useLocation();
  const { data: stockList } = useGetWatchlist();

  const stockData = useMemo(() => {
    return stockList?.flatMap((group) => group.items) ?? [];
  }, [stockList]);

  // Extract stock symbol (e.g., AAPL) from path like /stock/AAPL
  const stockTicker = pathname.split("/")[3];

  // define a stock item component
  const StockItem = ({ stock }: { stock: Stock }) => {
    const { data: stockPrice } = useGetStockPrice({ ticker: stock.ticker });
    const { mutateAsync: removeStock, isPending: isRemoving } =
      useRemoveStockFromWatchlist();
    const targetPath = isAStockTicker(stock.ticker)
      ? `/home/astock-preview?symbol=${encodeURIComponent(getAStockSymbol(stock.ticker))}`
      : `/home/stock/${encodeURIComponent(stock.ticker)}`;
    const activeTicker = decodeURIComponent(stockTicker || "");

    // transform data format to match StockMenuListItem expectation
    const transformedStock = useMemo(
      () => ({
        symbol: stock.symbol,
        companyName: stock.display_name,
        price: stockPrice?.price_formatted ?? "N/A",
        changePercent: stockPrice?.change_percent,
      }),
      [stock, stockPrice],
    );

    return (
      <StockMenuListItem
        stock={transformedStock}
        to={targetPath}
        isActive={activeTicker === stock.ticker}
        replace={!!stockTicker}
        isRemoving={isRemoving}
        onRemove={async () => {
          await removeStock(stock.ticker);
        }}
      />
    );
  };

  return (
    <StockMenu className="h-full">
      <StockMenuHeader>{t("home.watchlist")}</StockMenuHeader>
      <div className="scroll-container">
        {stockData?.map((stock) => (
          <StockItem key={stock.symbol} stock={stock} />
        ))}
      </div>
    </StockMenu>
  );
}

export default memo(StockList);
