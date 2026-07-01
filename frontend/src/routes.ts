import {
  index,
  layout,
  prefix,
  type RouteConfig,
  route,
} from "@react-router/dev/routes";

export default [
  index("app/redirect-to-home.tsx"),

  ...prefix("/home", [
    layout("app/home/_layout.tsx", [
      index("app/home/home.tsx"),
      route("/astock-preview", "app/home/astock-preview.tsx"),
      route("/astock-watchlist-scan", "app/home/astock-watchlist-scan.tsx"),
      route("/astock-memory", "app/home/astock-memory.tsx"),
      route("/fund-dashboard", "app/home/fund-dashboard.tsx"),
      route("/stock/:stockId", "app/home/stock.tsx"),
    ]),
  ]),

  route("/market", "app/market/agents.tsx"),

  // route("/ranking", "app/rank/board.tsx"),

  ...prefix("/agent", [
    route("/:agentName", "app/agent/chat.tsx"),
    route("/:agentName/config", "app/agent/config.tsx"),
  ]),

  ...prefix("/setting", [
    layout("app/setting/_layout.tsx", [
      index("app/setting/models.tsx"),
      route("/general", "app/setting/general.tsx"),
      route("/memory", "app/setting/memory.tsx"),
    ]),
  ]),

  // router for test components
  route("/test", "app/test.tsx"),
] satisfies RouteConfig;

