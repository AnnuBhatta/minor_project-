/*
 * Firebase Cloud Messaging service worker.
 *
 * Loaded from /firebase-messaging-sw.js?sid=<messagingSenderId> so the sender
 * id always matches the one configured on the page (VITE_FIREBASE_MESSAGING_SENDER_ID).
 * Receives background push notifications while the tab is closed and shows
 * a browser notification for the patient's guardian.
 */
importScripts('https://www.gstatic.com/firebasejs/10.14.1/firebase-app-compat.js');
importScripts('https://www.gstatic.com/firebasejs/10.14.1/firebase-messaging-compat.js');

const params = new URL(self.location.href).searchParams;
const senderId = params.get('sid');

if (senderId) {
  firebase.initializeApp({ messagingSenderId: senderId });
}

const messaging = firebase.messaging();

messaging.onBackgroundMessage((payload) => {
  const data = payload.data || {};
  const tier = data.tier;
  const fallbackTitle = tier === '1' ? '🚨 EMERGENCY ALERT' : 'VitalWatch Alert';
  const title = (payload.notification && payload.notification.title) || fallbackTitle;
  const body =
    (payload.notification && payload.notification.body) ||
    (payload.notification && payload.notification.title) ||
    'Check on your patient now.';

  self.registration.showNotification(title, {
    body,
    icon: '/emergency-icon.png',
    badge: '/emergency-icon.png',
    tag: data.alert_id || `tier-${tier || '0'}`,
    data: { url: data.type === 'emergency_alert' ? '/alerts' : '/alerts' },
  });

  self.addEventListener('notificationclick', (event) => {
    event.notification.close();
    event.waitUntil(clients.openWindow('/alerts'));
  });
});