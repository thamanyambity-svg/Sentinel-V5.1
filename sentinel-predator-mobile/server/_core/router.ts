import { router, publicProcedure } from "./trpc";
import { z } from "zod";
import { db } from "./db";
import { positions, orders } from "./schema";
import { eq } from "drizzle-orm";

/**
 * Schémas de Validation Zod
 */
const CreateOrderInput = z.object({
  symbol: z.string().min(1).max(10),
  type: z.enum(["BUY", "SELL"]),
  quantity: z.number().positive(),
  price: z.number().positive(),
  stopLoss: z.number().positive().optional(),
  takeProfit: z.number().positive().optional(),
});

const UpdatePositionInput = z.object({
  id: z.string(),
  quantity: z.number().nonnegative().optional(),
  currentPrice: z.number().positive().optional(),
});

/**
 * Trading Router
 */
const tradingRouter = router({
  /**
   * GET: Récupérer toutes les positions
   */
  getPositions: publicProcedure.query(async () => {
    try {
      const allPositions = await db.select().from(positions);
      return allPositions;
    } catch (error) {
      console.error("Erreur getPositions:", error);
      throw new Error("Impossible de récupérer les positions");
    }
  }),

  /**
   * GET: Récupérer une position par ID
   */
  getPosition: publicProcedure
    .input(z.object({ id: z.string() }))
    .query(async ({ input }) => {
      const position = await db
        .select()
        .from(positions)
        .where(eq(positions.id, input.id))
        .limit(1);

      if (!position.length) {
        throw new Error("Position non trouvée");
      }

      return position[0];
    }),

  /**
   * POST: Créer une nouvelle position
   */
  createPosition: publicProcedure
    .input(
      z.object({
        symbol: z.string(),
        quantity: z.number().positive(),
        entryPrice: z.number().positive(),
      })
    )
    .mutation(async ({ input }) => {
      const newPosition = await db
        .insert(positions)
        .values({
          symbol: input.symbol,
          // Need to convert to string because numeric fields in Supabase require string types in Drizzle inserts
          quantity: input.quantity.toString(),
          entryPrice: input.entryPrice.toString(),
          currentPrice: input.entryPrice.toString(),
          pnl: "0",
          pnlPercent: "0",
        })
        .returning();

      return newPosition[0];
    }),

  /**
   * PUT: Mettre à jour une position
   */
  updatePosition: publicProcedure
    .input(UpdatePositionInput)
    .mutation(async ({ input }) => {
      const updated = await db
        .update(positions)
        .set({
          ...(input.quantity !== undefined && { quantity: input.quantity.toString() }),
          ...(input.currentPrice !== undefined && { currentPrice: input.currentPrice.toString() }),
        })
        .where(eq(positions.id, input.id))
        .returning();

      return updated[0];
    }),

  /**
   * DELETE: Clôturer une position
   */
  closePosition: publicProcedure
    .input(z.object({ id: z.string() }))
    .mutation(async ({ input }) => {
      await db.delete(positions).where(eq(positions.id, input.id));
      return { success: true };
    }),

  /**
   * GET: Récupérer tous les ordres
   */
  getOrders: publicProcedure.query(async () => {
    const allOrders = await db.select().from(orders);
    return allOrders;
  }),

  /**
   * POST: Créer un nouvel ordre
   */
  createOrder: publicProcedure
    .input(CreateOrderInput)
    .mutation(async ({ input }) => {
      const newOrder = await db
        .insert(orders)
        .values({
          symbol: input.symbol,
          type: input.type,
          quantity: input.quantity.toString(),
          price: input.price.toString(),
          // Need to handle optional numeric strings
          ...(input.stopLoss !== undefined && { stopLoss: input.stopLoss.toString() }),
          ...(input.takeProfit !== undefined && { takeProfit: input.takeProfit.toString() }),
          status: "PENDING",
        })
        .returning();

      return newOrder[0];
    }),

  /**
   * PUT: Mettre à jour le statut d'un ordre
   */
  updateOrderStatus: publicProcedure
    .input(
      z.object({
        id: z.string(),
        status: z.enum(["PENDING", "FILLED", "CANCELLED"]),
      })
    )
    .mutation(async ({ input }) => {
      const updated = await db
        .update(orders)
        .set({ status: input.status })
        .where(eq(orders.id, input.id))
        .returning();

      return updated[0];
    }),

  /**
   * GET: Récupérer les métriques de marché
   */
  getMarketMetrics: publicProcedure.query(async () => {
    return {
      marketRisk: 42,
      vixFear: 18.5,
      verdict: "NEUTRAL",
      confidence: 65,
      marketOpen: true,
    };
  }),
});

import * as fs from "fs";

/**
 * Legacy API Support (To preserve backward compatibility with index.tsx)
 */
const MACRO_BIAS_PATH = "/Users/macbookpro/Downloads/bot_project/macro_bias.json";

/**
 * App Router Principal
 */
export const appRouter = router({
  trading: tradingRouter,
  getTradingData: publicProcedure.query(async () => {
    try {
      const data = JSON.parse(fs.readFileSync(MACRO_BIAS_PATH, "utf-8"));
      return {
        account: {
          balance: data.account?.balance || 0,
          equity: data.account?.equity || 0,
          marginLevel: data.account?.margin_level || 0,
          marketOpen: data.market?.is_open ?? true,
        },
        verdict: {
          bias: data.ai_analysis?.bias || "NEUTRAL",
          confidence: data.ai_analysis?.confidence || 50,
        },
        risk: {
          marketRisk: data.risk?.score || 30,
          vix: data.market?.vix || 15.0,
        },
        positions: data.positions || [],
      };
    } catch (e) {
      console.error("Error reading MT5 data:", e);
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
});

export type AppRouter = typeof appRouter;
