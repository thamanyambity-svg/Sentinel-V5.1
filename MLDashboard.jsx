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
    root: { background: "#050b18", minHeight: "100vh", color: "#e2e8f0", fontFamily: "'Inter', monospace", padding: "20px" },
    header: { display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 24, borderBottom: "1px solid #1e293b", paddingBottom: 16 },
    title: { fontSize: 24, fontWeight: "bold", color: "#60a5fa", letterSpacing: 1, textShadow: "0 0 10px rgba(96, 165, 250, 0.3)" },
    sub: { color: "#94a3b8", fontSize: 13, marginTop: 4 },
    tabs: { display: "flex", gap: 10, marginBottom: 24 },
    tab: (active) => ({
        padding: "8px 20px", borderRadius: 8, border: "none", cursor: "pointer",
        background: active ? "linear-gradient(135deg, #3b82f6, #2563eb)" : "#111827",
        color: active ? "#fff" : "#94a3b8",
        fontSize: 13, fontWeight: "600", transition: "all 0.2s ease",
        boxShadow: active ? "0 4px 12px rgba(59, 130, 246, 0.3)" : "none",
    }),
    card: (color) => ({
        background: "rgba(17, 24, 39, 0.8)", borderRadius: 12, padding: 18,
        border: `1px solid ${color ? color + "44" : "#1e293b"}`,
        backdropFilter: "blur(8px)",
    }),
    row: { display: "flex", alignItems: "center", gap: 12, marginBottom: 12 },
    badge: (color) => ({
        background: color + "22", color: color, padding: "2px 8px", borderRadius: 4, fontSize: 11, fontWeight: "bold", border: `1px solid ${color}44`
    }),
};

export default function MLDashboard() {
    const [tab, setTab] = useState("live");
    const [sel, setSel] = useState(null);
    
    // Live data state
    const [liveTicks, setLiveTicks] = useState({});
    const [positions, setPositions] = useState([]);
    const [account, setAccount] = useState({balance: 0, equity: 0, drawdown: 0});
    const [journal, setJournal] = useState([]);
    const [socket, setSocket] = useState(null);
    const [listening, setListening] = useState(false);
    const recognitionRef = useRef(null);
    const journalEndRef = useRef(null);

    // Auto-scroll journal
    useEffect(() => {
        if (journalEndRef.current) {
            journalEndRef.current.scrollIntoView({ behavior: "smooth" });
        }
    }, [journal]);
    
    // WebSocket & Polling
    useEffect(() => {
        const newSocket = io('http://localhost:5000');
        setSocket(newSocket);

        newSocket.on('connect', () => {
            console.log('✅ WebSocket Connected');
            newSocket.emit('subscribe_ticks');
        });

        newSocket.on('live_ticks', (data) => {
            if (data && data.ticks) {
                setLiveTicks(data.ticks);
            }
        });

        // Polling for REST data
        const fetchData = async () => {
            try {
                const [accRes, posRes, jouRes] = await Promise.all([
                    fetch('http://localhost:5000/api/v1/account'),
                    fetch('http://localhost:5000/api/v1/positions'),
                    fetch('http://localhost:5000/api/v1/journal')
                ]);
                
                const accData = await accRes.json();
                const posData = await posRes.json();
                const jouData = await jouRes.json();

                if (accData.status === "success") setAccount(accData.data);
                if (Array.isArray(posData.data)) setPositions(posData.data);
                if (Array.isArray(jouData)) setJournal(jouData);
            } catch (err) {
                console.error("❌ Polling error:", err);
            }
        };

        fetchData();
        const interval = setInterval(fetchData, 3000);

        return () => {
            newSocket.disconnect();
            clearInterval(interval);
        };
    }, []);

    // Voice Recognition Implementation
    const toggleVoice = useCallback(() => {
        if (listening) {
            recognitionRef.current?.stop();
            setListening(false);
            return;
        }

        const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
        if (!SpeechRecognition) {
            alert("Speech recognition not supported in this browser.");
            return;
        }

        const recognition = new SpeechRecognition();
        recognition.lang = 'fr-FR';
        recognition.continuous = false;
        recognition.interimResults = false;

        recognition.onresult = (event) => {
            const command = event.results[0][0].transcript.toLowerCase();
            console.log("🎤 Command recognized:", command);
            
            if (command.includes("pipeline")) setTab("pipeline");
            else if (command.includes("module")) setTab("modules");
            else if (command.includes("feature")) setTab("features");
            else if (command.includes("métrique") || command.includes("metric")) setTab("targets");
            else if (command.includes("live")) setTab("live");
            
            setListening(false);
        };

        recognition.onend = () => setListening(false);
        recognition.start();
        recognitionRef.current = recognition;
        setListening(true);
    }, [listening]);

    return (
        <div style={s.root}>
            {/* Header */}
            <div style={s.header}>
                <div>
                    <div style={s.title}>🧠 ALADDIN PRO V7 — Sentinel Sovereign</div>
                    <div style={s.sub}>Blackbox Intelligence · Swarm Orchestration · Live Execution</div>
                </div>
                
                <div style={{ display: "flex", gap: 16, alignItems: "center" }}>
                    <div style={{ textAlign: "right" }}>
                        <div style={{ fontSize: 11, color: "#64748b" }}>ACCOUNT EQUITY</div>
                        <div style={{ fontSize: 20, fontWeight: "bold", color: "#10b981" }}>${account.equity.toLocaleString()}</div>
                    </div>
                    <button onClick={toggleVoice} style={{ 
                        background: listening ? "#ef4444" : "#1e293b", 
                        border: "none", borderRadius: "50%", width: 44, height: 44, cursor: "pointer",
                        display: "flex", alignItems: "center", justifyContent: "center", fontSize: 20,
                        transition: "all 0.3s ease", boxShadow: listening ? "0 0 15px #ef4444" : "none"
                    }}>
                        {listening ? "🛑" : "🎤"}
                    </button>
                </div>
            </div>

            {/* Navigation */}
            <div style={s.tabs}>
                {[
                    ["live", "⚡ Live Command"],
                    ["pipeline", "🔄 Pipeline"],
                    ["modules", "📦 Modules"],
                    ["features", "📊 Features"],
                    ["targets", "🎯 Metrics"],
                ].map(([id, label]) => (
                    <button key={id} onClick={() => setTab(id)} style={s.tab(tab === id)}>{label}</button>
                ))}
            </div>

            {/* LIVE COMMAND VIEW */}
            {tab === "live" && (
                <div style={{ display: "grid", gridTemplateColumns: "1fr 380px", gap: 20 }}>
                    <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
                        {/* Market Overview */}
                        <div style={s.card("#3b82f6")}>
                            <div style={{ color: "#3b82f6", fontWeight: "bold", fontSize: 12, marginBottom: 16, letterSpacing: 1 }}>MARKET DEPTH — REAL TIME</div>
                            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(180px, 1fr))", gap: 12 }}>
                                {Object.entries(liveTicks).map(([sym, price]) => (
                                    <div key={sym} style={{ background: "#0f172a", borderRadius: 10, padding: "12px 16px", border: "1px solid #1e293b" }}>
                                        <div style={{ fontSize: 11, color: "#64748b" }}>{sym}</div>
                                        <div style={{ fontSize: 18, fontWeight: "bold", color: "#f8fafc", margin: "4px 0" }}>{price.toFixed(5)}</div>
                                        <div style={{ fontSize: 10, color: "#10b981" }}>● Live WebSocket</div>
                                    </div>
                                ))}
                            </div>
                        </div>

                        {/* Positions Heatmap */}
                        <div style={s.card("#10b981")}>
                            <div style={{ color: "#10b981", fontWeight: "bold", fontSize: 12, marginBottom: 16, letterSpacing: 1 }}>ACTIVE POSITIONS — HEATMAP</div>
                            {positions.length > 0 ? (
                                <div style={{ display: "flex", flexWrap: "wrap", gap: 10 }}>
                                    {positions.map((p, i) => (
                                        <div key={i} style={{ 
                                            padding: "12px", borderRadius: 8, minWidth: 140,
                                            background: p.pnl >= 0 ? "rgba(16, 185, 129, 0.1)" : "rgba(239, 68, 68, 0.1)",
                                            border: `1px solid ${p.pnl >= 0 ? "#10b98144" : "#ef444444"}`
                                        }}>
                                            <div style={{ display: "flex", justifyContent: "space-between", fontSize: 11 }}>
                                                <span style={{ fontWeight: "bold" }}>{p.symbol}</span>
                                                <span style={{ color: p.type.includes("BUY") ? "#10b981" : "#ef4444" }}>{p.type}</span>
                                            </div>
                                            <div style={{ fontSize: 18, fontWeight: "bold", margin: "8px 0" }}>${p.pnl.toFixed(2)}</div>
                                            <div style={{ fontSize: 10, color: "#94a3b8" }}>Vol: {p.volume} | {p.pnl_percent}%</div>
                                        </div>
                                    ))}
                                </div>
                            ) : (
                                <div style={{ textAlign: "center", padding: "40px 0", color: "#475569", fontSize: 13 }}>NO ACTIVE POSITIONS — STANDBY</div>
                            )}
                        </div>
                    </div>

                    {/* Execution Journal Sidebar */}
                    <div style={{ ...s.card("#f59e0b"), display: "flex", flexDirection: "column", height: "600px" }}>
                        <div style={{ color: "#f59e0b", fontWeight: "bold", fontSize: 12, marginBottom: 16, letterSpacing: 1 }}>EXECUTION JOURNAL — LIVE AUDIT</div>
                        <div style={{ flex: 1, overflowY: "auto", display: "flex", flexDirection: "column", gap: 12, paddingRight: 8 }}>
                            {journal.map((entry, i) => (
                                <div key={i} style={{ borderLeft: `2px solid ${entry.event.includes("TRADE") ? "#10b981" : "#3b82f6"}`, paddingLeft: 12, fontSize: 12 }}>
                                    <div style={{ display: "flex", justifyContent: "space-between", color: "#64748b", fontSize: 10 }}>
                                        <span>{entry.timestamp?.split('T')[1]?.substring(0, 8)}</span>
                                        <span style={{ fontWeight: "bold", color: "#94a3b8" }}>{entry.actor}</span>
                                    </div>
                                    <div style={{ color: "#e2e8f0", marginTop: 2, fontWeight: entry.event.includes("TRADE") ? "bold" : "normal" }}>
                                        {entry.event}: {entry.context?.asset || entry.context?.broker || "System Check"}
                                    </div>
                                    {entry.context?.status && (
                                        <div style={{ fontSize: 10, color: entry.context.status === "EXECUTED" ? "#10b981" : "#ef4444", marginTop: 2 }}>
                                            Status: {entry.context.status} | PnL: {entry.context.pnl}
                                        </div>
                                    )}
                                </div>
                            ))}
                            <div ref={journalEndRef} />
                        </div>
                    </div>
                </div>
            )}

            {/* PIPELINE VIEW */}
            {tab === "pipeline" && (
                <div>
                    <div style={{ display: "flex", alignItems: "center", justifyContent: "center", flexWrap: "wrap", gap: 10, marginBottom: 30 }}>
                        {PIPELINE.map((step, i) => (
                            <div key={i} style={{ display: "flex", alignItems: "center", gap: 10 }}>
                                <div style={{ background: step.color + "11", border: `1px solid ${step.color}`, borderRadius: 12, padding: "12px 20px", textAlign: "center", minWidth: 120 }}>
                                    <div style={{ fontSize: 24 }}>{step.icon}</div>
                                    <div style={{ fontSize: 12, color: step.color, fontWeight: "bold", marginTop: 4 }}>{step.label}</div>
                                </div>
                                {i < PIPELINE.length - 1 && <div style={{ color: "#1e293b", fontSize: 24 }}>→</div>}
                            </div>
                        ))}
                    </div>

                    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
                        {[
                            {
                                title: "PHASE 1 — TRAINING (OFFLINE)", color: "#3b82f6", steps: [
                                    "1. Collecter trade_log_all.jsonl (min 100 trades)",
                                    "2. python ml_feature_engine.py → features pkl",
                                    "3. python ml_trainer.py → model_xgb.pkl",
                                    "4. Valider: Precision > 58%, Recall > 55%",
                                    "5. Copier model_xgb.pkl → dossier MQL5/Files",
                                ]
                            },
                            {
                                title: "PHASE 2 — PREDICTION (LIVE)", color: "#10b981", steps: [
                                    "1. ml_predictor.py démarre avec engine.py",
                                    "2. Lit ticks_v3.json toutes les 500ms",
                                    "3. Score XGBoost → proba [0.0–1.0]",
                                    "4. Écrit ml_signal.json si proba > 0.62",
                                    "5. MQL5 lit IsMLSignalOK() avant chaque entrée",
                                ]
                            },
                        ].map((sec, i) => (
                            <div key={i} style={s.card(sec.color)}>
                                <div style={{ color: sec.color, fontWeight: "bold", fontSize: 13, marginBottom: 14 }}>{sec.title}</div>
                                {sec.steps.map((st, j) => (
                                    <div key={j} style={{ fontSize: 12, color: "#cbd5e1", marginBottom: 8, paddingLeft: 12, borderLeft: `1px solid ${sec.color}44` }}>{st}</div>
                                ))}
                            </div>
                        ))}
                    </div>
                </div>
            )}

            {/* MODULES VIEW */}
            {tab === "modules" && (
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
                    {MODULES.map(mod => (
                        <div key={mod.id} onClick={() => setSel(sel?.id === mod.id ? null : mod)}
                            style={{
                                background: "rgba(17, 24, 39, 0.8)", borderRadius: 12, padding: 18, cursor: "pointer",
                                border: `1px solid ${sel?.id === mod.id ? mod.color : "#1e293b"}`, transition: "all 0.3s ease",
                                transform: sel?.id === mod.id ? "translateY(-4px)" : "none"
                            }}>
                            <div style={s.row}>
                                <span style={{ fontSize: 24 }}>{mod.icon}</span>
                                <div>
                                    <div style={{ color: mod.color, fontWeight: "bold", fontSize: 14 }}>{mod.file}</div>
                                    <div style={{ color: "#94a3b8", fontSize: 12 }}>{mod.desc}</div>
                                </div>
                            </div>
                            {sel?.id === mod.id && (
                                <div style={{ marginTop: 12, paddingTop: 12, borderTop: "1px solid #1e293b" }}>
                                    {mod.features.map((f, i) => (
                                        <div key={i} style={{ fontSize: 11, color: "#cbd5e1", marginBottom: 6, paddingLeft: 12 }}>• {f}</div>
                                    ))}
                                    <div style={{ display: "flex", gap: 20, fontSize: 10, marginTop: 12 }}>
                                        <div>
                                            <div style={{ color: "#64748b", marginBottom: 4, fontWeight: "bold" }}>INPUTS</div>
                                            {mod.inputs.map((inp, i) => <div key={i} style={{ color: "#94a3b8" }}>← {inp}</div>)}
                                        </div>
                                        <div>
                                            <div style={{ color: "#64748b", marginBottom: 4, fontWeight: "bold" }}>OUTPUTS</div>
                                            {mod.outputs.map((out, i) => <div key={i} style={{ color: "#10b981" }}>→ {out}</div>)}
                                        </div>
                                    </div>
                                </div>
                            )}
                        </div>
                    ))}
                </div>
            )}

            {/* FEATURES VIEW */}
            {tab === "features" && (
                <div style={s.card("#8b5cf6")}>
                    <div style={{ color: "#94a3b8", fontSize: 13, marginBottom: 20 }}>
                        23 features construites depuis les logs JSONL — importance relative estimée (SHAP)
                    </div>
                    {FEATURES.map((f, i) => (
                        <div key={i} style={{ display: "flex", alignItems: "center", gap: 16, marginBottom: 12 }}>
                            <div style={{ width: 180, color: "#e2e8f0", fontSize: 13 }}>{f.name}</div>
                            <div style={s.badge(TYPE_COLORS[f.type])}>{f.type}</div>
                            <div style={{ flex: 1, background: "#0f172a", borderRadius: 6, height: 14, overflow: "hidden" }}>
                                <div style={{
                                    width: `${f.importance}%`, height: "100%",
                                    background: `linear-gradient(90deg, ${TYPE_COLORS[f.type]}, ${TYPE_COLORS[f.type]}aa)`,
                                    borderRadius: 6
                                }} />
                            </div>
                            <div style={{ color: "#94a3b8", fontSize: 12, width: 40, textAlign: "right" }}>{f.importance}</div>
                        </div>
                    ))}
                </div>
            )}

            {/* METRICS VIEW */}
            {tab === "targets" && (
                <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
                    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 20 }}>
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
                                <div style={{ color: sec.color, fontWeight: "bold", fontSize: 13, marginBottom: 16 }}>{sec.title}</div>
                                {sec.items.map(([k, v, d], j) => (
                                    <div key={j} style={{ display: "flex", justifyContent: "space-between", marginBottom: 10, alignItems: "flex-start" }}>
                                        <div style={{ color: "#94a3b8", fontSize: 12 }}>{k}</div>
                                        <div style={{ textAlign: "right" }}>
                                            <div style={{ color: sec.color, fontSize: 13, fontWeight: "bold" }}>{v}</div>
                                            <div style={{ color: "#475569", fontSize: 10 }}>{d}</div>
                                        </div>
                                    </div>
                                ))}
                            </div>
                        ))}
                    </div>
                    
                    <div style={{ ...s.card("#ef4444"), background: "rgba(239, 68, 68, 0.05)" }}>
                        <div style={{ color: "#ef4444", fontWeight: "bold", fontSize: 13, marginBottom: 12 }}>⚠️ AVERTISSEMENTS INSTITUTIONNELS</div>
                        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
                            {[
                                "Le ML ne crée pas d'edge — il filtre un edge DÉJÀ EXISTANT. Si la stratégie de base perd, le ML ne peut pas la sauver.",
                                "Minimum 100 trades réels avant d'entraîner — moins = surfit garanti.",
                                "Toujours valider sur OOS chronologique — jamais de shuffle aléatoire sur time series.",
                                "Re-entraîner toutes les semaines — le marché change, le modèle doit suivre.",
                            ].map((warn, i) => (
                                <div key={i} style={{ fontSize: 11, color: "#fca5a5", paddingLeft: 12, borderLeft: "2px solid #ef444444" }}>• {warn}</div>
                            ))}
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}
