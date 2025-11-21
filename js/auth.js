const isLocalhost = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1';
const isDualLocal = window.location.hostname === 'dual.local';
const API_BASE_URL =
  window.__AUDIOVOOK_API__ ||
  (isLocalhost
    ? `${window.location.protocol}//${window.location.hostname}:8000`
    : isDualLocal
      ? window.location.origin
      : 'https://api.audiovook.com');

// expose for inline scripts
window.__AVOOK_API_BASE__ = API_BASE_URL;

const originalFetch = window.fetch.bind(window);

function injectAuth(input, init) {
  const token = localStorage.getItem('av_jwt') || localStorage.getItem('audiovook_token');
  if (!token) return { input, init };

  const baseHeaders = init?.headers || (input instanceof Request ? input.headers : undefined);
  const headers = new Headers(baseHeaders || undefined);
  if (headers.has('Authorization')) return { input, init };

  headers.set('Authorization', `Bearer ${token}`);
  const nextInit = { ...(init || {}), headers };

  if (input instanceof Request) {
    return { input: new Request(input, nextInit), init: undefined };
  }
  return { input, init: nextInit };
}

window.fetch = (input, init) => {
  const { input: preparedInput, init: preparedInit } = injectAuth(input, init);
  return originalFetch(preparedInput, preparedInit);
};

function clearStoredSession(){
  localStorage.removeItem('av_jwt');
  localStorage.removeItem('audiovook_token');
  localStorage.removeItem('av_user');
}

async function setupLogoutButton(){
  const logoutBtn = document.getElementById('logoutBtn');
  if(!logoutBtn) return;

  const hasSession = Boolean(localStorage.getItem('av_jwt') || localStorage.getItem('audiovook_token'));
  if(!hasSession){
    logoutBtn.style.display = 'none';
    return;
  }

  const resetUi = () => {
    logoutBtn.textContent = 'Sessió tancada';
    logoutBtn.disabled = true;
    setTimeout(() => window.location.href = './index.html', 400);
  };

  logoutBtn.addEventListener('click', async () => {
    logoutBtn.disabled = true;
    logoutBtn.textContent = 'Sortint...';
    try {
      await originalFetch(`${API_BASE_URL}/auth/logout`, {
        method: 'POST',
        credentials: 'include'
      });
    } catch (err){
      console.warn('No s\'ha pogut contactar amb el servidor de logout', err);
    } finally {
      clearStoredSession();
      resetUi();
    }
  });
}

async function exchangeMagicTokenIfPresent() {
  const params = new URLSearchParams(window.location.search);
  const token = params.get('token');
  if (!token) return;

  try {
    const res = await originalFetch(`${API_BASE_URL}/auth/magic-login?token=${encodeURIComponent(token)}`, {
      credentials: 'include'
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok || !data.access_token) {
      throw new Error(data.detail || 'Magic login exchange failed');
    }

    localStorage.setItem('av_jwt', data.access_token);
    if (data.user) {
      localStorage.setItem('av_user', JSON.stringify(data.user));
    }
  } catch (err) {
    console.error('Magic login exchange failed', err);
  } finally {
    params.delete('token');
    const newUrl = `${window.location.pathname}${params.toString() ? `?${params.toString()}` : ''}${window.location.hash || ''}`;
    window.history.replaceState({}, '', newUrl);
  }
}

exchangeMagicTokenIfPresent();

document.addEventListener('DOMContentLoaded', setupLogoutButton);
