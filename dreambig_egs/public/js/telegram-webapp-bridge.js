/**
 * Telegram WebApp Bridge for Dream Big EGS
 * Detects Telegram WebApp context, closes Mini App upon successful submission,
 * and notifies the user to return to chat.
 */
(function() {
  if (typeof window === 'undefined') return;

  function initTelegramBridge() {
    if (window.Telegram && window.Telegram.WebApp) {
      try {
        window.Telegram.WebApp.ready();
        window.Telegram.WebApp.expand();
      } catch (e) {
        console.warn('[Telegram WebApp] Failed to expand:', e);
      }
    }
  }

  // Hook into Frappe Web Form after_save event
  if (window.frappe) {
    if (!frappe.web_form) frappe.web_form = {};
    if (!frappe.web_form.events) frappe.web_form.events = $({});

    frappe.web_form.events.on('after_save', function() {
      if (window.Telegram && window.Telegram.WebApp && window.Telegram.WebApp.initData) {
        // Show native alert and close webview back to chat
        setTimeout(function() {
          try {
            window.Telegram.WebApp.showAlert('Registration submitted successfully! Tap "🔄 I have registered" in chat to begin.', function() {
              window.Telegram.WebApp.close();
            });
          } catch(e) {
            window.Telegram.WebApp.close();
          }
        }, 800);
      }
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initTelegramBridge);
  } else {
    initTelegramBridge();
  }
})();
