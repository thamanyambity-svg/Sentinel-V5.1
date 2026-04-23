import {
  pgTable,
  text,
  numeric,
  timestamp,
  varchar,
  pgEnum,
} from "drizzle-orm/pg-core";
import { sql } from "drizzle-orm";

/**
 * Table: Positions
 */
export const positions = pgTable("positions", {
  id: text("id")
    .primaryKey()
    .default(sql`gen_random_uuid()`),
  symbol: varchar("symbol", { length: 10 }).notNull(),
  quantity: numeric("quantity", { precision: 18, scale: 8 }).notNull(),
  entryPrice: numeric("entry_price", { precision: 18, scale: 8 }).notNull(),
  currentPrice: numeric("current_price", { precision: 18, scale: 8 }).notNull(),
  pnl: numeric("pnl", { precision: 18, scale: 2 }).notNull().default("0"),
  pnlPercent: numeric("pnl_percent", { precision: 5, scale: 2 })
    .notNull()
    .default("0"),
  createdAt: timestamp("created_at").defaultNow(),
  updatedAt: timestamp("updated_at").defaultNow(),
});

/**
 * Table: Orders
 */
export const orders = pgTable("orders", {
  id: text("id")
    .primaryKey()
    .default(sql`gen_random_uuid()`),
  symbol: varchar("symbol", { length: 10 }).notNull(),
  type: pgEnum("order_type", ["BUY", "SELL"])("type").notNull(),
  quantity: numeric("quantity", { precision: 18, scale: 8 }).notNull(),
  price: numeric("price", { precision: 18, scale: 8 }).notNull(),
  stopLoss: numeric("stop_loss", { precision: 18, scale: 8 }),
  takeProfit: numeric("take_profit", { precision: 18, scale: 8 }),
  status: pgEnum("order_status", ["PENDING", "FILLED", "CANCELLED"])(
    "status"
  )
    .notNull()
    .default("PENDING"),
  createdAt: timestamp("created_at").defaultNow(),
  updatedAt: timestamp("updated_at").defaultNow(),
});

/**
 * Table: Users
 */
export const users = pgTable("users", {
  id: text("id")
    .primaryKey()
    .default(sql`gen_random_uuid()`),
  email: varchar("email", { length: 255 }).notNull().unique(),
  name: varchar("name", { length: 255 }),
  balance: numeric("balance", { precision: 18, scale: 2 })
    .notNull()
    .default("50000"),
  equity: numeric("equity", { precision: 18, scale: 2 })
    .notNull()
    .default("50000"),
  marginLevel: numeric("margin_level", { precision: 5, scale: 2 })
    .notNull()
    .default("0"),
  createdAt: timestamp("created_at").defaultNow(),
  updatedAt: timestamp("updated_at").defaultNow(),
});
