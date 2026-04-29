import { useState, useEffect, useCallback, useRef } from "react";
import io from 'socket.io-client';

const MODULES = [
    {
        id: 1,
        file: "ml_feature_engine.py",
        icon: "⚙️",
        color: "#3b82f6",
        title: "Feature Engine",
        desc: "Construction des features ML depuis les logs JSONL",
        features: [
            "23 features: ATR, RSI, ADX, spread, regime, session, R:R, heure UTC, jour semaine",
            "Rolling stats: mean/std ATR sur 10 derniers trades",
            "Label: WIN (1) / LOSS (0) sur net_profit",
            "Normalisation Z-score + clip des outliers à ±3σ",
            "Train/Val/Test split chronologique (70/15/15)",
        ],
        inputs: ["trade_log_all.jsonl", "signal_log.jsonl"],
        outputs: ["features_train.pkl", "features_test.pkl", "scaler.pkl"],
    },
    {
        id: 2,
        file: "ml_trainer.py",
        icon: "🧠",
        color: "#8b5cf6",
        title: "XGBoost Trainer",
        desc: "Entraînement + validation + export du modèle",
        features: [
            "XGBoost Classifier (LightGBM / sklearn fallback si non dispo)",
            "GridSearch: max_depth × n_estimators × learning_rate",
            "Validation Walk-Forward: IS → OOS rolling",
            "Threshold adaptatif: maximise F1 sur validation",
            "WFE: Walk-Forward Efficiency = OOS_F1 / IS_F1",
        ],
        inputs: ["features_train.pkl", "features_test.pkl"],
        outputs: ["model_xgb.pkl", "scaler.pkl", "threshold.json"],
    },
    {
        id: 3,
        file: "ml_predictor.py",
        icon: "🎯",
        color: "#10b981",
        title: "Predictor (temps réel)",
        desc: "Scoring live — intégré dans engine.py",
        features: [
            "Charge model_xgb.pkl + scaler.pkl au démarrage",
            "predict_signal(tick_data) → proba [0.0–1.0]",
            "Seuil configurable: MIN_CONFIDENCE = 0.62",
            "Écrit ml_signal.json (lu par le bot MQL5)",
            "Fallback rule-based si modèle absent ou expiré",
        ],
        inputs: ["ticks_v3.json", "model_xgb.pkl", "scaler.pkl"],
        outputs: ["ml_signal.json"],
    },
    {
        id: 4,
        file: "ml_signal.json",
        icon: "📡",
        color: "#f59e0b",
        title: "Signal JSON → MQL5",
        desc: "Bridge ML → Bot (lu à chaque tick)",
        features: [
            '{"sym":"XAUUSD","signal":1,"proba":0.74,"confidence":"HIGH"}',
            "signal: 1=BUY, -1=SELL, 0=NO_TRADE",
            "confidence: HIGH(>0.72) | MED(>0.62) | LOW(<0.62 = block)",
            "Latence: <5ms (lecture fichier local)",
            "Fallback: si absent → bot utilise règles classiques",
        ],
        inputs: ["ml_predictor.py output"],
        outputs: ["Lu par MQL5 IsMLSignalOK()"],
    },
];

const PIPELINE = [
    { label: "Logs MT5", color: "#64748b", icon: "📄" },
    { label: "Feature Engine", color: "#3b82f6", icon: "⚙️" },
    { label: "XGBoost Train", color: "#8b5cf6", icon: "🧠" },
    { label: "Model .pkl", color: "#6366f1", icon: "💾" },
    { label: "Predictor Live", color: "#10b981", icon: "🎯" },
    { label: "ml_signal.json", color: "#f59e0b", icon: "📡" },
    { label: "MQL5 Bot", color: "#ef4444", icon: "🤖" },
];

const FEATURES = [
    { name: "atr_at_entry", type: "Volatilité", importance: 92 },
    { name: "adx_at_entry", type: "Tendance", importance: 88 },
    { name: "rsi_at_entry", type: "Momentum", importance: 81 },
    { name: "regime", type: "Contexte", importance: 79 },
    { name: "spread_entry", type: "Coût", importance: 75 },
    { name: "hour_utc", type: "Session", importance: 71 },
    { name: "rr_ratio", type: "Risque", importance: 68 },
    { name: "atr_rolling_mean", type: "Volatilité", importance: 64 },
    { name: "rsi_momentum", type: "Momentum", importance: 61 },
    { name: "day_of_week", type: "Calendrier", importance: 47 },
    { name: "ema_gap_pct", type: "Tendance", importance: 43 },
    { name: "consec_losses", type: "Contexte", importance: 38 },
];

const TYPE_COLORS = {
    "Volatilité": "#3b82f6",
    "Tendance": "#8b5cf6",
    "Momentum": "#10b981",
    "Contexte": "#f59e0b",
    "Coût": "#ef4444",
    "Session": "#06b6d4",
    "Risque": "#ec4899",
    "Calendrier": "#84cc16",
};

const s = {
    root: { background: "#0f172a", minHeight: "100vh", color: "#e2e8f0", fontFamily: "monospace", padding: "16px" },
    header: { textAlign: "center", marginBottom: 20 },
    title: { fontSize: 22, fontWeight: "bold", color: "#60a5fa", letterSpacing: 2 },
    sub: { color: "#94a3b8", fontSize: 12, marginTop: 4 },
    tabs: { display: "flex", gap: 8, marginBottom: 20, justifyContent: "center" },
    tab: (active) => ({
        padding: "6px 16px", borderRadius: 6, border: "none", cursor: "pointer",
        background: active ? "#3b82f6" : "#1e293b",
        color: active ? "#fff" : "#94a3b8",
        fontSize: 12, fontFamily: "monospace",
    }),
    card: (color) => ({
        background: "#1e293b", borderRadius: 8, padding: 14,
        border: `1px solid ${color}44`,
    }),
    row: { display: "flex", alignItems: "center", gap: 10, marginBottom: 8 },
};

export default function MLDashboard() {
    const [tab, setTab] = useState("live");
    const [sel, setSel] = useState(null);
    
    // Live data state
    const [liveTicks, setLiveTicks] = useState({});
    const [positions, setPositions] = useState([]);
    const [account, setAccount] = useState({balance: 0, equity: 0});
    const [socket, setSocket] = useState(null);
    const [voiceActive, setVoiceActive] = useState(false);
    const [listening, setListening] = useState(false);
    const recognitionRef = useRef(null);
    
    // WebSocket connection
    useEffect(() => {
        const newSocket = io('http://localhost:5000');
        newSocket.on('connect', () => {
            console.log('WebSocket connected');
            newSocket.emit('subscribe_ticks');
        });

    return (
        <div style={s.root}>
            {/* Header */}
            <div style={s.header}>
                <div style={s.title}>🧠 ALADDIN PRO V6 — Couche ML</div>
                <div style={s.sub}>XGBoost Signal Classifier · Feature Engineering · Live Predictor</div>
            </div>

            {/* Tabs */}
            <div style={s.tabs}>
                {[
                    ["pipeline", "🔄 Pipeline"],
                    ["modules", "📦 Modules"],
                    ["features", "📊 Features"],
                    ["targets", "🎯 Métriques"],
                ].map(([id, label]) => (
                    <button key={id} onClick={() => setTab(id)} style={s.tab(tab === id)}>{label}</button>
                ))}
            </div>

            {/* PIPELINE */}
            {tab === "pipeline" && (
                <div>
                    {/* Flèches pipeline */}
                    <div style={{ display: "flex", alignItems: "center", justifyContent: "center", flexWrap: "wrap", gap: 4, marginBottom: 24 }}>
                        {PIPELINE.map((step, i) => (
                            <div key={i} style={{ display: "flex", alignItems: "center", gap: 4 }}>
                                <div style={{ background: step.color + "22", border: `1px solid ${step.color}`, borderRadius: 8, padding: "8px 12px", textAlign: "center", minWidth: 90 }}>
                                    <div style={{ fontSize: 18 }}>{step.icon}</div>
                                    <div style={{ fontSize: 10, color: step.color, fontWeight: "bold", marginTop: 2 }}>{step.label}</div>
                                </div>
                                {i < PIPELINE.length - 1 && <div style={{ color: "#475569", fontSize: 18 }}>→</div>}
                            </div>
                        ))}
                    </div>

                    {/* Phases */}
                    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
                        {[
                            {
                                title: "PHASE 1 — OFFLINE (1x/semaine)", color: "#3b82f6", steps: [
                                    "1. Collecter trade_log_all.jsonl (min 100 trades)",
                                    "2. python ml_feature_engine.py → features pkl",
                                    "3. python ml_trainer.py → model_xgb.pkl",
                                    "4. Valider: Precision > 58%, Recall > 55%",
                                    "5. Copier model_xgb.pkl → dossier MQL5/Files",
                                ]
                            },
                            {
                                title: "PHASE 2 — LIVE (temps réel)", color: "#10b981", steps: [
                                    "1. ml_predictor.py démarre avec engine.py",
                                    "2. Lit ticks_v3.json toutes les 500ms",
                                    "3. Score XGBoost → proba [0.0–1.0]",
                                    "4. Écrit ml_signal.json si proba > 0.62",
                                    "5. MQL5 lit IsMLSignalOK() avant chaque entrée",
                                ]
                            },
                        ].map((sec, i) => (
                            <div key={i} style={s.card(sec.color)}>
                                <div style={{ color: sec.color, fontWeight: "bold", fontSize: 11, marginBottom: 10 }}>{sec.title}</div>
                                {sec.steps.map((st, j) => (
                                    <div key={j} style={{ fontSize: 11, color: "#cbd5e1", marginBottom: 5, paddingLeft: 8 }}>{st}</div>
                                ))}
                            </div>
                        ))}
                    </div>

                    {/* Params clés */}
                    <div style={{ background: "#1e293b", borderRadius: 8, padding: 14, marginTop: 12, border: "1px solid #334155" }}>
                        <div style={{ color: "#f59e0b", fontWeight: "bold", fontSize: 11, marginBottom: 8 }}>⚙️ PARAMÈTRES CLÉS ML</div>
                        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 8 }}>
                            {[
                                { k: "MIN_CONFIDENCE", v: "0.62", d: "Seuil minimum pour trader" },
                                { k: "HIGH_CONFIDENCE", v: "0.72", d: "Lot size +25%" },
                                { k: "MIN_TRADES_TRAIN", v: "100", d: "Trades minimum pour entraîner" },
                                { k: "RETRAIN_INTERVAL", v: "7 jours", d: "Re-entraîner chaque semaine" },
                                { k: "FEATURE_WINDOW", v: "10 trades", d: "Rolling stats sur N trades" },
                                { k: "TEST_SPLIT", v: "70/15/15", d: "Train/Val/Test chronologique" },
                            ].map((it, i) => (
                                <div key={i} style={{ background: "#0f172a", borderRadius: 6, padding: 8 }}>
                                    <div style={{ color: "#60a5fa", fontSize: 10, fontWeight: "bold" }}>{it.k}</div>
                                    <div style={{ color: "#f0f9ff", fontSize: 14, margin: "2px 0" }}>{it.v}</div>
                                    <div style={{ color: "#64748b", fontSize: 9 }}>{it.d}</div>
                                </div>
                            ))}
                        </div>
                    </div>
                </div>
            )}

            {/* MODULES */}
            {tab === "modules" && (
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
                    {MODULES.map(mod => (
                        <div key={mod.id} onClick={() => setSel(sel?.id === mod.id ? null : mod)}
                            style={{
                                background: "#1e293b", borderRadius: 10, padding: 14, cursor: "pointer",
                                border: `1px solid ${sel?.id === mod.id ? mod.color : "#334155"}`, transition: "border-color 0.2s"
                            }}>
                            <div style={s.row}>
                                <span style={{ fontSize: 20 }}>{mod.icon}</span>
                                <div>
                                    <div style={{ color: mod.color, fontWeight: "bold", fontSize: 12 }}>{mod.file}</div>
                                    <div style={{ color: "#94a3b8", fontSize: 10 }}>{mod.desc}</div>
                                </div>
                            </div>
                            {sel?.id === mod.id && (
                                <div>
                                    {mod.features.map((f, i) => (
                                        <div key={i} style={{ fontSize: 10, color: "#cbd5e1", marginBottom: 4, paddingLeft: 8 }}>• {f}</div>
                                    ))}
                                    <div style={{ display: "flex", gap: 12, fontSize: 9, marginTop: 8 }}>
                                        <div>
                                            <div style={{ color: "#64748b", marginBottom: 2 }}>INPUTS</div>
                                            {mod.inputs.map((inp, i) => <div key={i} style={{ color: "#94a3b8" }}>← {inp}</div>)}
                                        </div>
                                        <div>
                                            <div style={{ color: "#64748b", marginBottom: 2 }}>OUTPUTS</div>
                                            {mod.outputs.map((out, i) => <div key={i} style={{ color: "#10b981" }}>→ {out}</div>)}
                                        </div>
                                    </div>
                                </div>
                            )}
                        </div>
                    ))}
                </div>
            )}

            {/* FEATURES */}
            {tab === "features" && (
                <div>
                    <div style={{ color: "#94a3b8", fontSize: 11, marginBottom: 12 }}>
                        23 features construites depuis les logs JSONL — importance relative estimée (SHAP)
                    </div>
                    {FEATURES.map((f, i) => (
                        <div key={i} style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 8 }}>
                            <div style={{ width: 160, color: "#e2e8f0", fontSize: 11 }}>{f.name}</div>
                            <div style={{
                                background: TYPE_COLORS[f.type] + "33", color: TYPE_COLORS[f.type],
                                borderRadius: 4, padding: "1px 6px", fontSize: 9, width: 70, textAlign: "center"
                            }}>{f.type}</div>
                            <div style={{ flex: 1, background: "#1e293b", borderRadius: 4, height: 12 }}>
                                <div style={{
                                    width: `${f.importance}%`, height: "100%",
                                    background: `linear-gradient(90deg, ${TYPE_COLORS[f.type]}, ${TYPE_COLORS[f.type]}88)`,
                                    borderRadius: 4
                                }} />
                            </div>
                            <div style={{ color: "#94a3b8", fontSize: 11, width: 35, textAlign: "right" }}>{f.importance}</div>
                        </div>
                    ))}
                </div>
            )}

            {/* MÉTRIQUES */}
            {tab === "targets" && (
                <div>
                    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, marginBottom: 16 }}>
                        {[
                            {
                                title: "SEUILS DE DÉPLOIEMENT ML", color: "#10b981", items: [
                                    ["Precision (trades retenus):", "> 58%", "Évite les faux positifs"],
                                    ["Recall (trades capturés):", "> 52%", "Capture assez de vrais gains"],
                                    ["ROC-AUC:", "> 0.62", "Discrimination >chance"],
                                    ["WFE (IS→OOS):", "> 0.50", "Modèle généralisable"],
                                    ["Trades minimum train:", "≥ 100", "Pas assez = pas fiable"],
                                ]
                            },
                            {
                                title: "IMPACT ATTENDU SUR LE BOT", color: "#3b82f6", items: [
                                    ["Trades filtrés:", "-20 à -35%", "Moins mais meilleurs"],
                                    ["Win Rate:", "+5 à +12pts", "Gain mesurable"],
                                    ["Profit Factor:", "+0.15 à +0.40", "Amélioration réaliste"],
                                    ["Max Drawdown:", "-2 à -6%", "Moins de mauvaises entrées"],
                                    ["Sharpe Ratio:", "+0.2 à +0.6", "Meilleur risque/rendement"],
                                ]
                            },
                        ].map((sec, i) => (
                            <div key={i} style={s.card(sec.color)}>
                                <div style={{ color: sec.color, fontWeight: "bold", fontSize: 11, marginBottom: 10 }}>{sec.title}</div>
                                {sec.items.map(([k, v, d], j) => (
                                    <div key={j} style={{ display: "flex", justifyContent: "space-between", marginBottom: 7, alignItems: "flex-start" }}>
                                        <div style={{ color: "#94a3b8", fontSize: 10 }}>{k}</div>
                                        <div style={{ textAlign: "right" }}>
                                            <div style={{ color: sec.color, fontSize: 11, fontWeight: "bold" }}>{v}</div>
                                            <div style={{ color: "#475569", fontSize: 9 }}>{d}</div>
                                        </div>
                                    </div>
                                ))}
                            </div>
                        ))}
                    </div>
                    <div style={{ background: "#1e293b", borderRadius: 8, padding: 14, border: "1px solid #ef444433" }}>
                        <div style={{ color: "#ef4444", fontWeight: "bold", fontSize: 11, marginBottom: 8 }}>⚠️ AVERTISSEMENTS INSTITUTIONNELS</div>
                        {[
                            "Le ML ne crée pas d'edge — il filtre un edge DÉJÀ EXISTANT. Si la stratégie de base perd, le ML ne peut pas la sauver.",
                            "Minimum 100 trades réels avant d'entraîner — moins = surfit garanti.",
                            "Toujours valider sur OOS chronologique — jamais de shuffle aléatoire sur time series.",
                            "Re-entraîner toutes les semaines — le marché change, le modèle doit suivre.",
                            "Garder le fallback rule-based actif — si le modèle expire, le bot continue.",
                        ].map((warn, i) => (
                            <div key={i} style={{ fontSize: 10, color: "#fca5a5", marginBottom: 6, paddingLeft: 8 }}>• {warn}</div>
                        ))}
                    </div>
                </div>
            )}
        </div>
    );
}
