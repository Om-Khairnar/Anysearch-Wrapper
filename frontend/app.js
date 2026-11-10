const form = document.getElementById('search-form');
const topicInput = document.getElementById('topic');
const statusEl = document.getElementById('status');
const resultsEl = document.getElementById('results');

function setStatus(message, type = '') {
  statusEl.textContent = message;
  statusEl.className = 'status';
  if (type) {
    statusEl.classList.add(type);
  }
}

function normalizeQueries(rawText) {
  const text = (rawText || '').trim();
  if (!text) return [];

  try {
    const parsed = JSON.parse(text);
    if (Array.isArray(parsed)) {
      return parsed
        .map((item) => typeof item === 'string' ? item.trim() : (item && item.query ? String(item.query).trim() : ''))
        .filter(Boolean);
    }
    if (typeof parsed === 'string' && parsed.trim()) {
      return [parsed.trim()];
    }
  } catch (error) {
    // not JSON, fall through to line-based parsing
  }

  return text
    .split(/\n+/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function renderResults(items) {
  resultsEl.innerHTML = '';

  if (!items || items.length === 0) {
    resultsEl.innerHTML = '<p>No results found for this request.</p>';
    return;
  }

  items.forEach((item) => {
    const card = document.createElement('article');
    card.className = 'result-card';

    const title = document.createElement('h2');
    title.textContent = item.title || 'Untitled result';

    const text = document.createElement('p');
    text.textContent = item.content || 'No description available.';

    if (item.url) {
      const link = document.createElement('a');
      link.href = item.url;
      link.target = '_blank';
      link.rel = 'noreferrer';
      link.textContent = item.url;
      card.appendChild(link);
    }

    card.appendChild(title);
    card.appendChild(text);
    resultsEl.appendChild(card);
  });
}

form.addEventListener('submit', async (event) => {
  event.preventDefault();

  const rawValue = topicInput.value;
  const queries = normalizeQueries(rawValue);

  if (!queries.length) {
    setStatus('Please enter at least one query.', 'error');
    return;
  }

  setStatus('Searching…', 'success');
  resultsEl.innerHTML = '';

  try {
    const response = await fetch('/api/search', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ queries }),
    });

    const payload = await response.json();

    if (!response.ok) {
      const message = payload.error || 'Request failed while searching.';
      setStatus(message, 'error');
      return;
    }

    const items = Array.isArray(payload.results) ? payload.results : [];
    renderResults(items);
    const queryLabel = queries.length === 1 ? 'query' : 'queries';
    setStatus(`Showing ${items.length} result${items.length === 1 ? '' : 's'} across ${queries.length} ${queryLabel}.`, 'success');
  } catch (error) {
    setStatus('Unable to connect to the search backend. Please try again.', 'error');
  }
});
