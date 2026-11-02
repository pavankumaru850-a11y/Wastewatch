# WasteWatch mobile app

Expo + Expo Router + TypeScript. Citizen-facing: capture, GPS, AI detection
preview, submit, offline queue, my reports, profile.

## What's actually verified

- `npx tsc --noEmit` passes clean across the whole app.
- `npx expo export --platform android` successfully bundled all 1448 modules
  with Metro (the real React Native bundler) -- this catches import errors,
  unresolved dependencies, and syntax problems that a type-checker alone
  would miss. No errors.
- Two real bugs were caught and fixed this way: `expo-file-system`'s SDK 57
  API replaced `documentDirectory`/`copyAsync` with `File`/`Paths` classes,
  and an earlier draft used AsyncStorage v3 (renamed `multiRemove`
  to `removeMany`. Both call sites were updated to match what's actually
  installed, not what older docs/training data would suggest.

## What's NOT verified

No physical device or simulator was available while building this, so
**nothing here has actually been tapped through on a phone.** Camera
capture, GPS permission prompts, and the SQLite offline queue are
implemented against the documented Expo APIs and the bundle compiles, but
runtime behavior on real hardware is untested. Test on a real device before
relying on this for a demo.

## Setup

```bash
cd mobile
npm install
cp .env.example .env
```

Edit `.env` and set `EXPO_PUBLIC_API_URL` -- there is deliberately no
localhost fallback (see `constants/config.ts`). Options:

```bash
# Same Wi-Fi as your backend:
EXPO_PUBLIC_API_URL=http://192.168.1.42:8000

# Different network (recommended -- works from anywhere):
ngrok http 8000
EXPO_PUBLIC_API_URL=https://xxxx.ngrok-free.app
```

Then:

```bash
npx expo start
```

Scan the QR code with Expo Go, or press `a`/`i` for an emulator.

## How the offline queue works

1. Report captured with no connectivity -> photo copied to permanent app
   storage, row written to a local SQLite table with status
   `PENDING_UPLOAD` (`database/db.ts`).
2. `services/useNetworkSync.ts` listens for connectivity via NetInfo; when
   the phone comes back online, it automatically calls
   `services/sync.ts#syncPendingReports()`.
3. Each pending report is uploaded via the normal `POST /api/reports`
   endpoint. A row is only deleted after the server confirms success --
   a failed attempt is marked `FAILED` (with the error) and retried on the
   next sync pass, not silently dropped.
4. The Pending Uploads screen (`app/pending-sync.tsx`) shows the queue and
   has a manual "Sync now" button for when you don't want to wait.

## Screens

Splash (`index.tsx`) -> Login/Register -> Home (network + GPS status, main
actions) -> Camera (capture -> GPS -> AI detect with bounding-box overlay ->
submit, or straight to offline queue if there's no connection) -> My
Reports -> Report Details -> Pending Uploads -> Profile.

## Known gaps against the original spec

- No splash *image/logo* asset, just a styled loading screen with the
  brand colors -- functionally equivalent, not visually designed.
- Gallery picker (submit from an existing photo, not just the live camera)
  isn't built.
- Low-bandwidth image compression is a fixed `quality: 0.7` JPEG on
  capture, not adaptive to connection speed.
