# Deploy WasteWatch on Render

The Render Blueprint at the repository root deploys the FastAPI backend,
PostgreSQL, and the React dashboard. The mobile app is a separate Android
build made with Expo/EAS; Render does not host the native app.

## Low-cost demo limitations

This Blueprint uses Render's free plans to minimize cost. It is for demos,
not production:

- The API sleeps after 15 minutes without traffic and can take about a minute
  to wake.
- The API has no persistent disk. Uploaded report and cleanup photos can be
  lost when the service restarts, sleeps, or redeploys.
- AI inference is disabled on the free API service. Reports can still be
  submitted, but need human review.
- The free PostgreSQL database expires 30 days after it is created. Export
  important data before it expires.
- The dashboard is hosted as a free static site.

For ongoing use, use a paid API service with a persistent disk (or external
object storage), and a paid PostgreSQL plan. Re-enable AI only after choosing
a service plan with enough memory to load the model.

## 1. Push the deployment files to GitHub

Render deploys from the connected Git repository. Ensure the repository's
`main` branch contains `render.yaml` and the application files.

## 2. Create the Render services

1. Sign in at [render.com](https://render.com).
2. Select **New +** → **Blueprint**.
3. Connect the GitHub repository containing WasteWatch and select `main`.
4. Review the resources before applying: `wastewatch-api` (Free), the free
   `wastewatch-db` PostgreSQL database, and `wastewatch-dashboard` (static).
5. Set the prompted values:
   - `ADMIN_EMAIL`: the email for your dashboard administrator.
   - `ADMIN_PASSWORD`: a unique password of at least 8 characters. Do not use
     the local demo password.
   - `VITE_API_URL`: the public HTTPS URL of `wastewatch-api`, with no trailing
     slash (for example, `https://wastewatch-api.onrender.com`).
6. Apply the Blueprint and wait for all three services to finish deploying.

If you don't know the API URL when Render asks, finish the API deployment,
copy its `onrender.com` URL from the Render dashboard, then open
`wastewatch-dashboard` → **Environment**, set `VITE_API_URL` to that URL, and
save/redeploy the dashboard.

## 3. Verify the deployment

- Open `https://<your-api>.onrender.com/api/health`; it should return
  `{"status":"healthy"}`.
- Open the dashboard's `onrender.com` URL and sign in with `ADMIN_EMAIL` and
  `ADMIN_PASSWORD`.
- Register a citizen account from the mobile app or the API, submit a report,
  and confirm it appears in the dashboard. On this free configuration, the
  report will need human review because AI inference is disabled.

## 4. Build the Android app

Set `EXPO_PUBLIC_API_URL` to the backend's HTTPS URL in `mobile/.env`, then
build an APK with EAS:

```powershell
cd mobile
npm install
npm install --global eas-cli
eas login
eas build --platform android --profile preview
```

The backend URL is embedded in the APK at build time. Rebuild the app if the
backend URL changes. Do not commit `.env` files or Render secrets.

## Upgrade from demo to persistent AI service

1. Change the API plan in `render.yaml` to a paid plan with sufficient memory
   for the bundled model.
2. Attach a paid persistent disk mounted at `/data` to preserve uploaded
   photos, or change the app to use external object storage.
3. Upgrade PostgreSQL to a paid plan before the free database expires.
4. Set `MODEL_PATH` to the deployed model path (for example
   `/app/models/best.pt`) and redeploy.
5. Restrict `CORS_ORIGINS` to the dashboard's exact HTTPS origin.

See [Render's free-instance limitations](https://render.com/docs/free) and
[persistent disk documentation](https://render.com/docs/disks) before
choosing a production configuration.
