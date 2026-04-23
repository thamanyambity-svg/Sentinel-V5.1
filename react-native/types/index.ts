// types/index.ts
export interface Position {
  id: string;
  symbol: string;
  quantity: number;
  entryPrice: number;
  currentPrice: number;
  pnl: number;
  pnlPercent: number;
  type: 'LONG' | 'SHORT';
}

export interface Order {
  id: string;
  symbol: string;
  type: 'BUY' | 'SELL';
  orderType: 'MARKET' | 'LIMIT' | 'STOP';
  quantity: number;
  price: number;
  status: 'PENDING' | 'FILLED' | 'CANCELLED';
  timestamp: string;
}

export interface AccountData {
  balance: number;
  equity: number;
  marginLevel: number;
  marginUsed: number;
  marginFree: number;
  currency: string;
}

export interface MLSignal {
  sentiment: 'BULLISH' | 'NEUTRAL' | 'BEARISH';
  confidence: number; // 0-100
  symbol: string;
  reasoning: string;
  timestamp: string;
}

export interface BacktestMetrics {
  totalReturn: number;
  profitFactor: number;
  winRate: number;
  sharpeRatio: number;
  maxDrawdown: number;
  trades: number;
}

export interface MarketData {
  health: any;
  account: AccountData;
  positions: Position[];
  orders: Order[];
  mlSignal: MLSignal;
  backtest: BacktestMetrics;
}

export interface WSMessage {
  type: 'connection' | 'market_update' | 'subscription' | 'error' | 'pong';
  timestamp: string;
  data?: any;
  status?: string;
  message?: string;
}
