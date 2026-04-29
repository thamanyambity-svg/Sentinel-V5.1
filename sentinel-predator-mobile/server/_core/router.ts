import { initTRPC } from "@trpc/server";
import { z } from "zod";
import fs from "fs";
import path from "path";

const t = initTRPC.create();
export const publicProcedure = t.procedure;
export const router = t.router;

const MT5_FILES_DIR = "/Users/macbookpro/Library/Application Support/net.metaquotes.wine.metatrader5/drive_c/users/user/AppData/Roaming/MetaQuotes/Terminal/Common/Files";
const STATUS_PATH = path.join(MT5_FILES_DIR, "status.json");
const TICKS_PATH = path.join(MT5_FILES_DIR, "ticks_v3.json");
const MACRO_BIAS_PATH = path.join(MT5_FILES_DIR, "macro_bias.json");

export const appRouter = router({
  getTradingData: publicProcedure.query(async () => {
    try {
      const response = await fetch("http://localhost:5000/api/v1/dashboard");
      const json = await response.json();
      if (json.status === "success") {
        const data = json.data;
        return {
          account: {
            balance: data.account?.balance || 0,
            equity: data.account?.equity || 0,
            marginLevel: data.account?.drawdown || 0,
            marketOpen: data.account?.trading_enabled ?? true,
          },
          verdict: {
            bias: data.ml?.decision || "NEUTRAL",
            confidence: data.ml?.confidence || 0,
            reasoning: data.ml?.reasoning || "",
          },
          risk: {
            marketRisk: data.ml?.signal_strength || 30,
            vix: data.ml?.fundamental?.market_mood || "NEUTRAL",
          },
          positions: data.account?.positions || [],
          history: data.ticks?.history || {},
        };
      }
      
      // Fallback to file reading if Flask is down
      try {
        const stats = JSON.parse(fs.readFileSync(STATUS_PATH, "utf-8"));
        const ticks = JSON.parse(fs.readFileSync(TICKS_PATH, "utf-8"));
        const macro = JSON.parse(fs.readFileSync(MACRO_BIAS_PATH, "utf-8"));
        
        return {
          account: {
            balance: stats.balance || 0,
            equity: stats.equity || 0,
            marginLevel: stats.margin_level || 0,
            marketOpen: true,
          },
          verdict: {
            bias: macro.bias || "NEUTRAL",
            confidence: macro.confidence || 0,
            reasoning: macro.reasoning || "",
          },
          risk: {
            marketRisk: 30,
            vix: "NEUTRAL",
          },
          positions: stats.positions || [],
          history: {},
        };
      } catch (fileErr) {
        return null;
      }
    } catch (e) {
      console.error("tRPC Error:", e);
      return null;
    }
  }),

  getTerminalLogs: publicProcedure.query(async () => {
    try {
      const data = JSON.parse(fs.readFileSync(MACRO_BIAS_PATH, "utf-8"));
      return data.logs || [];
    } catch (e) {
      return [];
    }
  }),

  getNewsFeed: publicProcedure.query(async () => {
    try {
      const NEWS_CACHE_PATH = "/Users/macbookpro/Downloads/bot_project/news_cache.json";
      if (fs.existsSync(NEWS_CACHE_PATH)) {
        return JSON.parse(fs.readFileSync(NEWS_CACHE_PATH, "utf-8"));
      }
      return [];
    } catch (e) {
      console.error("Error reading news cache:", e);
      return [];
    }
  }),

  executeTrade: publicProcedure
    .input(z.object({
      symbol: z.string(),
      side: z.enum(["BUY", "SELL"]),
      volume: z.number().default(0.1),
    }))
    .mutation(async ({ input }) => {
      try {
        const response = await fetch("http://localhost:5000/api/v1/trade", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(input),
        });
        return await response.json();
      } catch (e) {
        console.error("Error executing trade:", e);
        throw new Error("Failed to execute trade");
      }
    }),
});

export type AppRouter = typeof appRouter;
