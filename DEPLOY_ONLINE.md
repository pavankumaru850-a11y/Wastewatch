# Put WasteWatch online so friends can use the phone app (no laptop needed)

You need: a free GitHub account, a free Render account (render.com), a free Expo account (expo.dev).
Cost: Render "starter" web service is about $7/month (free plans sleep, lose photos and are too small for the AI).
If the AI crashes with "out of memory" in the Render logs, change `plan: starter` to `plan: standard` in render.yaml.

## 1. Train and deploy the AI model first (on your PC)
`training\train_classifier.py --binary ... --deploy` creates `backend\models\best.pt`. It gets baked into the server image.
(No model yet? You can still go online: reports are saved and staff review them. Add the model later and redeploy.)

## 2. Put the project on GitHub
1. github.com -> New repository -> name `wastewatch`, **Private**.
2. In cmd, inside your `ww` folder:
```
git init
git add .
git commit -m "WasteWatch"
git branch -M main
git remote add origin https://github.com/YOUR_NAME/wastewatch.git
git push -u origin main
```
(`best.pt` is included because it is in `backend\models`. Skip step 1 if you have none.)

## 3. Deploy the backend on Render
1. render.com -> **New +** -> **Blueprint** -> connect GitHub -> choose `wastewatch`.
2. Render reads `render.yaml`. It asks for two values: `ADMIN_EMAIL` and `ADMIN_PASSWORD` (this is your dashboard admin login, 8+ characters).
3. Click **Apply**. The first build takes 10-20 minutes (the AI runtime is large).
4. When it says **Live**, open `https://YOUR-SERVICE.onrender.com/api/health`. It must show `{"status":"healthy"}`.
   Write down that address (it is your backend URL).

## 4. Point the phone app at it
Edit `mobile\.env`:
```
EXPO_PUBLIC_API_URL=https://YOUR-SERVICE.onrender.com
```
No slash at the end.

## 5. Build the APK and send it to friends
```
cd mobile
npm install
npm install -g eas-cli
eas login
eas build -p android --profile preview
```
- Say yes when it asks to create a project / keystore.
- After ~15 minutes it prints a download link for the `.apk`. Send that link to your friends.
- On their Android phone: open the link, download, allow "Install unknown apps", install.
- Friends tap **Register** in the app to make their own citizen account. No Expo account is needed for them.
- The URL from step 4 is built INTO the APK. If you change the backend address, build a new APK.

## 6. Dashboard for you (admin)
Run it on your PC: `cd dashboard`, create `dashboard\.env` with `VITE_API_URL=https://YOUR-SERVICE.onrender.com`,
then `npm install` and `npm run dev`. Log in with the `ADMIN_EMAIL` / `ADMIN_PASSWORD` from step 3.
Create staff accounts from **Users & Staff**.

## Quick test without paying (laptop must stay on)
`ngrok http 8000` + `EXPO_PUBLIC_API_URL=https://xxxx.ngrok-free.app` + `npx expo start --tunnel`.
