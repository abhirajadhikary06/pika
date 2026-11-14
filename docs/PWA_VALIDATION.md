# PWA validation checklist

## Local build checks

From `frontend/` run:

```sh
npm ci
npm run typecheck
npm run build
npm run check:pwa
```

The artifact check verifies that the built manifest, icons, screenshots, offline page, root service worker, API cache exclusion, and Vercel cache rules are present.

## Browser checks

Use a production build over HTTPS, install/open Pika, then inspect **DevTools → Application**:

- Confirm the manifest identity is `/`, the icon variants load, and the app opens in standalone mode.
- Confirm `/sw.js` controls the root scope and the current precache has the current build version.
- Confirm the app shell and offline page are cached, while authenticated API calls and POST requests are not in Cache Storage.
- Confirm IndexedDB contains user/workspace-scoped ticket records and outbox operations.
- Go offline, reopen the app, view a previously loaded ticket, create a ticket, add a reply, and change a ticket field. Confirm each local change is visible and marked pending.
- Restore the connection. Confirm queued operations become synced and appear on the server once, even if the request is repeated.
- Change the same field in two browser profiles and verify Pika asks which version to keep. Change different fields and verify they merge without replacing either change.
- Close and reopen the app with a pending operation. Confirm it returns to the queue and syncs when the app can reach the API.
- Expire the access token, then sync. Confirm Pika preserves the outbox while sign-in is required.
- Throttle the network and test reconnects; don't rely only on `navigator.onLine` to decide whether a request succeeded.
- Deploy a new build while an old tab is open. Confirm the update prompt appears, choosing Update reloads once, and choosing Later keeps the current tab usable.
- Confirm upload and download controls are disabled offline and show the online-only explanation. Test the authorized upload/download flow while online.

Repeat the install, offline startup, and reconnect checks on Android Chrome and iOS Safari. Background Sync is optional and must not be required for the fallback triggers (startup, visibility, online, timer, and after-write sync) to work.

## Deployment header checks

After deploying the frontend, inspect response headers for `/`, `/index.html`, `/manifest.webmanifest`, `/sw.js`, and one hashed `/assets/...` file. The HTML, manifest, and service worker should revalidate promptly; hashed assets should return a long-lived immutable cache policy.

## Push notifications

Browser push is not part of the current PWA release. If added later, test permission only after a button gesture, subscription ownership and removal, delivery failure cleanup, notification clicks, and iOS Home Screen installation. Apple documents Web Push for Home Screen web apps on iOS 16.4 and later: https://developer.apple.com/documentation/usernotifications/sending-web-push-notifications-in-web-apps-and-browsers.
