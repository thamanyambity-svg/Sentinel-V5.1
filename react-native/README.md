# SENTINEL PREDATOR - React Native Mobile App

Institutional-grade trading platform for iOS and Android devices.

## 📱 Platform Support

- **iOS 13+** (iPhone/iPad)
- **Android 5.0+** (Phones/Tablets)
- **Web** (Expo Web)

## 🚀 Quick Start

### Prerequisites
- Node.js 16+ and npm/yarn
- Expo CLI: `npm install -g expo-cli`
- iOS: Xcode 13+ (for iOS development)
- Android: Android Studio (for Android development)

### Installation

```bash
# Install dependencies
npm install
# or
yarn install

# Start development server
npm start
# or
yarn start

# Run on iOS simulator
npm run ios

# Run on Android emulator
npm run android

# Run on web
npm run web
```

## 📁 Project Structure

```
sentinel-predator/
├── App.tsx                    # Root navigation setup
├── screens/                   # Tab screen components
│   ├── DashboardScreen.tsx
│   ├── TerminalScreen.tsx
│   ├── CreateOrderScreen.tsx
│   ├── IntelligenceScreen.tsx
│   ├── SettingsScreen.tsx
│   └── PositionDetailScreen.tsx
├── components/                # Reusable UI components
│   ├── Card.tsx
│   ├── Header.tsx
│   ├── VerdictCard.tsx
│   └── PositionItem.tsx
├── context/                   # State management
│   └── WSContext.tsx          # WebSocket data context
├── constants/                 # Design tokens & config
│   └── Colors.ts
├── types/                     # TypeScript definitions
│   └── index.ts
├── package.json
├── tsconfig.json
├── app.json
└── README.md
```

## 🎨 Design System

### Colors
- **Background**: `#0d1117` (Primary), `#161b22` (Secondary)
- **Text**: `#e2e8f0` (Primary), `#8b949e` (Secondary)
- **Status**: 
  - Bullish: `#10b981` (Green)
  - Bearish: `#ef4444` (Red)
  - Neutral: `#f59e0b` (Amber)
  - Primary: `#0891b2` (Cyan)

### Typography
- **Titles**: Inter Bold 700 (24pt)
- **Body**: Inter Regular 400 (14pt)
- **Mono Data**: JetBrains Mono 600 (13pt)
- **Labels**: Inter 600 (10pt, uppercase, tracked)

### Spacing Scale
- xs: 4px
- sm: 8px
- md: 12px
- lg: 16px
- xl: 20px
- xxl: 24px

## 🔗 Real-Time Data Integration

The app connects to a WebSocket server (`localhost:5001`) for streaming market data.

### WebSocket Connection Flow

```typescript
// Automatically handled by WSProvider context
const { isConnected, marketData, error } = useWS();

// Subscribe to specific channels
ws.send(JSON.stringify({
  type: 'subscribe',
  channel: 'market_data'
}));

// Receive updates every 2 seconds
// {
//   type: 'market_update',
//   timestamp: '2024-04-21T10:33:00Z',
//   data: { health, account, positions, ticks, ml_signal, backtest }
// }
```

### API Endpoints (via Flask Backend)

- `GET /api/v1/health` - System status
- `GET /api/v1/account` - Account balance & equity
- `GET /api/v1/positions` - Open positions list
- `GET /api/v1/ticks` - Real-time price data
- `GET /api/v1/ml` - AI trading signals
- `GET /api/v1/backtest` - Strategy metrics

## 🎯 Core Features

### 1. Dashboard (Home)
- Account overview (balance, equity, margin)
- AI verdict card (BULLISH/NEUTRAL/BEARISH sentiment)
- Market risk metrics
- Bot status and countdown
- Open positions with P&L
- Active orders list

### 2. Market Terminal
- Real-time market data feed
- Symbol scanning and filtering
- Terminal-style output (colored by type)
- Tap to view position details

### 3. Order Creation
- Symbol selector
- Buy/Sell toggle
- Quantity input
- Limit/Market/Stop order types
- Stop Loss & Take Profit inputs
- Real-time P&L preview

### 4. Intelligence Dossier
- Executive summary
- Technical analysis (supports, resistance, RSI)
- Fundamental analysis
- Risk identification
- Trading recommendations

### 5. News Feed
- Real-time financial news
- Impact indicators
- Source attribution
- Sentiment tagging

### 6. Settings
- Account management
- 2FA authentication
- Trading preferences (currency, risk, leverage)
- App appearance (dark/light, font size)
- About & legal

## 🔐 Security

- WebSocket over WSS (TLS) in production
- Authentication token management (AsyncStorage)
- Secure credential storage
- 2FA support
- API key rotation

## 🧪 Testing

```bash
# Type checking
npm run typecheck

# Linting
npm run lint

# Format code
npm run format
```

## 📦 Build & Deployment

### iOS
```bash
eas build --platform ios
```

### Android
```bash
eas build --platform android
```

### Web
```bash
npm run web
# Then use Netlify or Vercel for hosting
```

## 🔄 Fallback Behavior

If WebSocket is unavailable:
- Mock data is displayed
- App remains fully functional
- Clear indication of offline status
- Automatic reconnection attempts (every 5 seconds)

## 🚨 Error Handling

- Network error banners
- Graceful degradation
- Retry mechanisms
- Error logging to console

## 📊 Performance Optimizations

- React.memo() for expensive components
- FlatList for large datasets (no ScrollView + .map())
- Lazy loading of screens
- Debounced input handlers
- Image caching with Expo

## 📝 Development Notes

- All functions are TypeScript typed
- Use `useWS()` hook for data access
- Follow design token naming (Colors, Typography, Spacing)
- Use SafeAreaView for notch support
- Test on both iOS and Android simulators

## 🤝 Contributing

1. Create feature branch: `git checkout -b feature/feature-name`
2. Follow code style with ESLint
3. Type all functions properly
4. Test on multiple devices
5. Submit pull request

## 📄 License

Proprietary - SENTINEL PREDATOR © 2024

---

**Contact**: support@sentinel.pro
**Documentation**: [See Design.md in parent directory]
