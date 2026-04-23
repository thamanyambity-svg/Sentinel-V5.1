import { ExpoConfig, ConfigContext } from 'expo/config';

export default ({ config }: ConfigContext): ExpoConfig => ({
  ...config,
  name: 'SENTINEL PREDATOR',
  slug: 'sentinel-predator-mobile',
  version: '1.0.0',
  orientation: 'portrait',
  // icon: './assets/images/icon.png',
  scheme: 'sentinel-predator',
  userInterfaceStyle: 'automatic',
  newArchEnabled: true,
  ios: {
    supportsTablet: true,
    bundleIdentifier: 'com.ambity.sentinel.predator'
  },
  android: {
    /* 
    adaptiveIcon: {
      foregroundImage: './assets/images/adaptive-icon.png',
      backgroundColor: '#0d1117'
    },
    */
    package: 'com.ambity.sentinel.predator'
  },
  web: {
    bundler: 'metro',
    output: 'static',
    // favicon: './assets/images/favicon.png'
  },
  plugins: [
  ],
  experiments: {
    typedRoutes: true
  }
});
