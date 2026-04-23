import express from "express";
import cors from "cors";
import * as trpcExpress from "@trpc/server/adapters/express";
import { appRouter } from "./_core/router";
import { setupWebSocket } from "./_core/websocket";
import { createServer } from "http";
import * as dotenv from "dotenv";

dotenv.config();

const app = express();

// Middleware
app.use(cors());
app.use(express.json());

// Points de terminaison TRPC intégrés à Express
app.use(
  "/trpc",
  trpcExpress.createExpressMiddleware({
    router: appRouter,
    createContext: ({ req, res }) => {
      // Intégrer l'authentification et les en-têtes plus tard
      return { req, res };
    },
  })
);

// Route d'état pour Express
app.get("/health", (req, res) => {
  res.json({ status: "ok", service: "Sentinel Predator Mobile API" });
});

// Configure Webhook for TradingView / MT5 Alerts
import { db } from "./_core/db";
import { orders } from "./_core/schema";

app.post("/api/webhook/trading", async (req, res) => {
  try {
    const { symbol, type, quantity, price, secret } = req.body;
    
    // Simple Secret Verification
    if (secret !== process.env.JWT_SECRET) {
      return res.status(401).json({ error: "Unauthorized / Invalid Secret" });
    }

    if (!symbol || !type || !quantity || !price) {
      return res.status(400).json({ error: "Missing required trading payload fields" });
    }

    // Insert order directly via ORM
    const newOrder = await db.insert(orders).values({
      symbol,
      type,
      quantity: quantity.toString(),
      price: price.toString(),
      status: "PENDING"
    }).returning();

    console.log(`[WEBHOOK] Order placed: ${type} ${quantity} ${symbol}`);
    res.status(200).json({ success: true, order: newOrder[0] });

  } catch (error) {
    console.error("[WEBHOOK] Error parsing trading alert:", error);
    res.status(500).json({ error: "Internal Server Error" });
  }
});

// Création du serveur HTTP et fixation du WebSocket
const server = createServer(app);
setupWebSocket(server);

const PORT = process.env.PORT || 3000;

server.listen(PORT, () => {
  console.log(`🚀 Sentinel Predator Express Server running on http://localhost:${PORT}`);
  console.log(`🔌 WebSocket server attached on ws://localhost:${PORT}`);
});
