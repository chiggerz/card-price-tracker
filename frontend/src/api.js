const DEFAULT_BASE_URL = 'http://127.0.0.1:8000';

export const API_BASE_URL =
  window.__CARD_TRACKER_API_BASE_URL__ ||
  new URLSearchParams(window.location.search).get('apiBaseUrl') ||
  DEFAULT_BASE_URL;

async function request(path, options = {}) {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: {
      'Content-Type': 'application/json',
      ...(options.headers || {}),
    },
    ...options,
  });

  let payload = null;
  try {
    payload = await response.json();
  } catch {
    payload = null;
  }

  if (!response.ok) {
    const detail = payload?.detail || 'Request failed.';
    throw new Error(detail);
  }

  return payload;
}

export function fetchSets() {
  return request('/sets');
}

export function fetchPlayers(setName) {
  const params = new URLSearchParams({ set_name: setName });
  return request(`/players?${params.toString()}`);
}

export function fetchCardTypes(setName, playerName) {
  const params = new URLSearchParams({ set_name: setName, player_name: playerName });
  return request(`/card-types?${params.toString()}`);
}

export function searchStructured(payload) {
  return request('/search/structured', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}
