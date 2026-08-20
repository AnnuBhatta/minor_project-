/*
 * Thin wrapper around the Firebase compat SDK loaded from the gstatic CDN
 * (see index.html). Every call is guarded: if the CDN scripts or the
 * VITE_FIREBASE_* environment variables are missing, the app keeps working
 * and FCM registration is simply skipped.
 */

const CONFIG = {
  apiKey: import.meta.env.VITE_FIREBASE_API_KEY,
  authDomain: import.meta.env.VITE_FIREBASE_AUTH_DOMAIN,
  databaseURL: import.meta.env.VITE_FIREBASE_DATABASE_URL,
  projectId: import.meta.env.VITE_FIREBASE_PROJECT_ID,
  storageBucket: import.meta.env.VITE_FIREBASE_STORAGE_BUCKET,
  messagingSenderId: import.meta.env.VITE_FIREBASE_MESSAGING_SENDER_ID,
  appId: import.meta.env.VITE_FIREBASE_APP_ID,
};

const VAPID_KEY = import.meta.env.VITE_FIREBASE_VAPID_KEY;

let messagingPromise = null;

export function isFirebaseConfigured() {
  return Boolean(
    window.firebase &&
      window.firebase.messaging &&
      CONFIG.apiKey &&
      CONFIG.messagingSenderId &&
      VAPID_KEY
  );
}

function getMessaging() {
  if (!messagingPromise) {
    messagingPromise = new Promise((resolve) => {
      try {
        if (!isFirebaseConfigured()) {
          resolve(null);
          return;
        }
        const existing = window.firebase.apps && window.firebase.apps[0];
        const app = existing || window.firebase.initializeApp(CONFIG);
        resolve(window.firebase.messaging(app));
      } catch (err) {
        console.warn('Firebase messaging init failed:', err);
        resolve(null);
      }
    });
  }
  return messagingPromise;
}

export async function getFcmToken() {
  try {
    const messaging = await getMessaging();
    if (!messaging) return null;
    return await messaging.getToken({ vapidKey: VAPID_KEY });
  } catch (err) {
    console.warn('FCM token fetch failed:', err);
    return null;
  }
}