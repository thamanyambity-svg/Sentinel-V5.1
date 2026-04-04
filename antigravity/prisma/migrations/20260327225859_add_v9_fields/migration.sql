-- CreateTable
CREATE TABLE "TradeSignal" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "ticket" INTEGER NOT NULL,
    "symbol" TEXT NOT NULL,
    "type" TEXT NOT NULL,
    "openPrice" REAL NOT NULL,
    "closePrice" REAL NOT NULL,
    "profit" REAL NOT NULL,
    "duration" INTEGER NOT NULL,
    "closedAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "v9Confluence" REAL,
    "v9MlProb" REAL,
    "v9Regime" TEXT
);

-- CreateIndex
CREATE UNIQUE INDEX "TradeSignal_ticket_key" ON "TradeSignal"("ticket");

-- CreateIndex
CREATE INDEX "TradeSignal_closedAt_idx" ON "TradeSignal"("closedAt");
