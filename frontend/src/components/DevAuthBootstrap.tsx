import { useEffect } from 'react';

export function DevAuthBootstrap() {
  // Dev auth bootstrap - auto-set JWT if not present (local dev only)
  useEffect(() => {
    const isLocalhost =
      window.location.hostname === 'localhost' ||
      window.location.hostname === '127.0.0.1' ||
      window.location.hostname === '::1';

    if (!import.meta.env.DEV && !isLocalhost) return;
    if (localStorage.getItem('flowforge_token')) return;

    const bootstrap = async () => {
      // Prefer backend-minted dev token (works in docker compose prod build).
      try {
        const res = await fetch('/api/v1/dev/token');
        if (res.ok) {
          const data = (await res.json()) as { token?: string };
          if (data.token) {
            localStorage.setItem('flowforge_token', data.token);
            window.location.reload();
            return;
          }
        }
      } catch {
        // ignore
      }

      // Fallback to Vite-provided build-time token (dev server / some builds).
      const devToken = import.meta.env.VITE_DEV_JWT as string | undefined;
      if (devToken) {
        localStorage.setItem('flowforge_token', devToken);
        window.location.reload();
      }
    };

    void bootstrap();
  }, []);

  return null;
}
