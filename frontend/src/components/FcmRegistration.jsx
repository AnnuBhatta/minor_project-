import { useEffect } from "react";
import { getFcmToken, isFirebaseConfigured } from "../firebase";

/*
 * Renders nothing. Once mounted (on any authenticated route) it:
 *   1. Asks for notification permission.
 *   2. Registers the Firebase messaging service worker.
 *   3. Requests the device FCM token and posts it to
 *      POST /api/auth/update-fcm-token/ so the backend can push emergency
 *      alerts to THIS device (patient or guardian).
 *
 * Everything is best-effort: missing Firebase config, denied permission or
 * a failed request never blocks the UI.
 */
export default function FcmRegistration() {
  useEffect(() => {
    let cancelled = false;

    (async () => {
      if (!isFirebaseConfigured()) {
        console.warn("Firebase FCM is not configured — skipping push registration.");
        return;
      }

      const accessToken = localStorage.getItem("access_token");
      if (!accessToken) return;

      if (!("Notification" in window)) return;
      if (Notification.permission === "denied") return;

      if (Notification.permission === "default") {
        try {
          await Notification.requestPermission();
        } catch (err) {
          console.warn("Notification permission request failed:", err);
        }
      }
      if (Notification.permission !== "granted") return;

      if ("serviceWorker" in navigator) {
        try {
          const senderId = import.meta.env.VITE_FIREBASE_MESSAGING_SENDER_ID;
          await navigator.serviceWorker.register(
            `/firebase-messaging-sw.js${senderId ? `?sid=${encodeURIComponent(senderId)}` : ""}`
          );
        } catch (err) {
          console.warn("Service worker registration failed:", err);
        }
      }

      const token = await getFcmToken();
      if (!token || cancelled) return;

      // Avoid re-posting the same token on every page load.
      if (localStorage.getItem("fcm_token") === token) return;

      try {
        const res = await fetch("/api/auth/update-fcm-token/", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${accessToken}`,
          },
          body: JSON.stringify({ fcm_token: token }),
        });
        if (res.ok) {
          localStorage.setItem("fcm_token", token);
        } else {
          console.warn("Failed to save FCM token to backend:", await res.text());
        }
      } catch (err) {
        console.warn("Error saving FCM token:", err);
      }
    })();

    return () => {
      cancelled = true;
    };
  }, []);

  return null;
}