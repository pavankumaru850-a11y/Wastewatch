/**
 * config.ts
 *
 * API_BASE_URL comes ONLY from EXPO_PUBLIC_API_URL (set in .env). This is
 * deliberate -- the spec is explicit that the mobile app must never
 * hard-code localhost/127.0.0.1, because the phone and the dev machine
 * are usually not on the same network. Set EXPO_PUBLIC_API_URL to:
 *
 *   - a LAN address (http://192.168.x.x:8000) when phone + PC share Wi-Fi
 *   - an ngrok HTTPS URL (https://xxxx.ngrok-free.app) for remote dev
 *   - your production API (https://api.your-domain.com) for a real build
 *
 * See ../.env.example and ../README.md.
 */
export const API_BASE_URL: string | null = process.env.EXPO_PUBLIC_API_URL || null;

export const MAX_UPLOAD_MB = 10;
