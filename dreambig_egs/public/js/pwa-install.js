/**
 * DREAM BIG - PWA Lifecycle & Installation Handler
 * Registers the Service Worker and presents native install prompts on mobile & desktop browsers.
 */
(function() {
  if (typeof window === 'undefined') return;

  // 1. Service Worker Registration
  if ('serviceWorker' in navigator) {
    window.addEventListener('load', function() {
      navigator.serviceWorker.register('/sw.js', { scope: '/' })
        .then(function(reg) {
          console.log('[DREAM BIG PWA] Service Worker active with scope:', reg.scope);
        })
        .catch(function(err) {
          console.warn('[DREAM BIG PWA] Service Worker registration failed:', err);
        });
    });
  }

  // 2. Install Prompt Interaction
  let deferredPrompt = null;

  window.addEventListener('beforeinstallprompt', function(e) {
    // Prevent immediate automatic browser banner
    e.preventDefault();
    deferredPrompt = e;

    // Show custom install triggers if available
    showPWAInstallBanner();
  });

  function showPWAInstallBanner() {
    // Check if user has already dismissed this in current session
    if (sessionStorage.getItem('pwa_install_dismissed')) return;

    // Avoid duplicate banners
    if (document.getElementById('dreambig-pwa-install-bar')) return;

    const banner = document.createElement('div');
    banner.id = 'dreambig-pwa-install-bar';
    banner.className = 'dreambig-pwa-banner';
    banner.innerHTML = `
      <div class="dreambig-pwa-content">
        <img src="/assets/dreambig_egs/icons/dreambig-icon.svg" alt="DreamBig" class="dreambig-pwa-icon" />
        <div class="dreambig-pwa-text">
          <strong>Install DREAM BIG App</strong>
          <span>Add to your home screen for instant access to your 5Ds goals!</span>
        </div>
      </div>
      <div class="dreambig-pwa-actions">
        <button id="pwa-install-btn" class="dreambig-pwa-btn-install">Install</button>
        <button id="pwa-dismiss-btn" class="dreambig-pwa-btn-dismiss" title="Dismiss">&times;</button>
      </div>
    `;

    document.body.appendChild(banner);

    document.getElementById('pwa-install-btn').addEventListener('click', function() {
      if (deferredPrompt) {
        deferredPrompt.prompt();
        deferredPrompt.userChoice.then(function(choiceResult) {
          if (choiceResult.outcome === 'accepted') {
            console.log('[DREAM BIG PWA] User accepted installation prompt');
          }
          deferredPrompt = null;
          banner.remove();
        });
      }
    });

    document.getElementById('pwa-dismiss-btn').addEventListener('click', function() {
      sessionStorage.setItem('pwa_install_dismissed', 'true');
      banner.remove();
    });
  }

  window.addEventListener('appinstalled', function() {
    console.log('[DREAM BIG PWA] Successfully installed as standalone app');
    const banner = document.getElementById('dreambig-pwa-install-bar');
    if (banner) banner.remove();
  });
})();
