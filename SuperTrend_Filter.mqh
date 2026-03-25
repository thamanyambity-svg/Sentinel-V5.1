//+------------------------------------------------------------------+
//|  SuperTrend_Filter.mqh                                           |
//|  Filtre SuperTrend — inspiré EA31337                             |
//|                                                                  |
//|  INSTALLATION :                                                  |
//|  1. Copier dans MQL5/Include/SuperTrend_Filter.mqh               |
//|  2. Dans AladdinPro_V719_TrapHunter.mq5 ajouter en haut :        |
//|     #include "SuperTrend_Filter.mqh"                             |
//|                                                                  |
//|  USAGE :                                                          |
//|  int  dir = SuperTrendDir(sym, tf);                               |
//|             retourne +1 (bullish) / -1 (bearish) / 0 (erreur)    |
//|  bool ok  = SuperTrendBullish(sym, tf);                           |
//|  bool ok  = SuperTrendBearish(sym, tf);                           |
//+------------------------------------------------------------------+
#property copyright "Ambity Project"
#property strict

//------------------------------------------------------------------
// SuperTrendDir()
//
// Calcule la direction du SuperTrend sur les bougies FERMÉES.
// Algorithme : ATR de Wilder + bandes haute/basse lissées.
//
//  sym      — symbole       (ex: "XAUUSD")
//  tf       — timeframe     (ex: PERIOD_M5)
//  period   — période ATR   (défaut : 10)
//  mult     — multiplicateur ATR  (défaut : 3.0)
//  lookback — bougies fermées à charger (min period+2, défaut : 50)
//
//  Retourne :
//   +1  close > ligne SuperTrend  → tendance haussière
//   -1  close < ligne SuperTrend  → tendance baissière
//    0  données insuffisantes
//------------------------------------------------------------------
int SuperTrendDir(string sym, ENUM_TIMEFRAMES tf,
                  int period   = 10,
                  double mult  = 3.0,
                  int lookback = 50)
{
    if(lookback < period + 2) lookback = period + 2;
    int total = lookback + 1;   // +1 pour la prev_close du premier bar

    double highs[], lows[], closes[];
    // Non-series : index 0 = bougie la plus ancienne, index total-1 = la plus récente
    // On copie à partir du bar 1 pour n'utiliser que des bougies fermées
    if(CopyHigh (sym, tf, 1, total, highs)  < total) { PrintFormat("[ST] %s — données insuffisantes (CopyHigh)", sym);  return 0; }
    if(CopyLow  (sym, tf, 1, total, lows)   < total) { PrintFormat("[ST] %s — données insuffisantes (CopyLow)",  sym);  return 0; }
    if(CopyClose(sym, tf, 1, total, closes) < total) { PrintFormat("[ST] %s — données insuffisantes (CopyClose)",sym);  return 0; }

    //------ ATR via Wilder (RMA) ------------------------------------
    double atr[];
    ArrayResize(atr, total);
    ArrayInitialize(atr, 0.0);

    // Seed : moyenne simple sur les 'period' premières TR
    double sum = 0.0;
    for(int i = 1; i <= period; i++)
    {
        double tr = MathMax(highs[i] - lows[i],
                   MathMax(MathAbs(highs[i] - closes[i - 1]),
                           MathAbs(lows[i]  - closes[i - 1])));
        sum += tr;
    }
    atr[period] = sum / period;

    // Lissage Wilder vers le bar le plus récent
    for(int i = period + 1; i < total; i++)
    {
        double tr = MathMax(highs[i] - lows[i],
                   MathMax(MathAbs(highs[i] - closes[i - 1]),
                           MathAbs(lows[i]  - closes[i - 1])));
        atr[i] = (atr[i - 1] * (period - 1) + tr) / period;
    }

    //------ Bandes SuperTrend + direction ---------------------------
    double upperBand = 0.0, lowerBand = 0.0;
    int    trend     = 1;           // +1 = haussier par défaut

    for(int i = period; i < total; i++)
    {
        double mid      = (highs[i] + lows[i]) * 0.5;
        double rawUpper = mid + mult * atr[i];
        double rawLower = mid - mult * atr[i];

        if(i == period)
        {
            upperBand = rawUpper;
            lowerBand = rawLower;
        }
        else
        {
            // Bande haute : ne remonte que si rawUpper est plus bas OU si le close
            // précédent a cassé la bande (invalide l'ancienne valeur)
            upperBand = (rawUpper < upperBand || closes[i - 1] > upperBand)
                        ? rawUpper : upperBand;
            // Bande basse : ne descend que si rawLower est plus haut OU si le close
            // précédent est passé sous la bande
            lowerBand = (rawLower > lowerBand || closes[i - 1] < lowerBand)
                        ? rawLower : lowerBand;
        }

        // Flip de tendance
        if(trend == 1)
        {
            if(closes[i] < lowerBand) trend = -1;
        }
        else
        {
            if(closes[i] > upperBand) trend =  1;
        }
    }

    return trend;
}

//------------------------------------------------------------------
// Retourne true si le SuperTrend est haussier
//------------------------------------------------------------------
bool SuperTrendBullish(string sym, ENUM_TIMEFRAMES tf,
                       int period = 10, double mult = 3.0)
{
    return SuperTrendDir(sym, tf, period, mult) == 1;
}

//------------------------------------------------------------------
// Retourne true si le SuperTrend est baissier
//------------------------------------------------------------------
bool SuperTrendBearish(string sym, ENUM_TIMEFRAMES tf,
                       int period = 10, double mult = 3.0)
{
    return SuperTrendDir(sym, tf, period, mult) == -1;
}
