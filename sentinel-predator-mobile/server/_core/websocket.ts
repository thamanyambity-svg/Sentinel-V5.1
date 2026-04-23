import { WebSocketServer } from "ws";
import { Server } from "http";

export function setupWebSocket(server: Server) {
  const wss = new WebSocketServer({ server });

  wss.on("connection", (ws) => {
    console.log("Client WebSocket connecté");

    // Envoyer les données initiales
    ws.send(
      JSON.stringify({
        type: "INITIAL_DATA",
        data: {
          marketRisk: 42,
          vixFear: 18.5,
        },
      })
    );

    // Simuler les mises à jour temps réel (ou connecter à vos logs/MT5 bridge)
    const interval = setInterval(() => {
      ws.send(
        JSON.stringify({
          type: "PRICE_UPDATE",
          data: {
            symbol: "XAUUSD",
            price: 2445.5 + (Math.random() - 0.5) * 2,
            timestamp: new Date().toISOString(),
          },
        })
      );
    }, 1000);

    ws.on("close", () => {
      console.log("Client WebSocket déconnecté");
      clearInterval(interval);
    });

    ws.on("error", (error) => {
      console.error("WebSocket error:", error);
    });
  });
}
