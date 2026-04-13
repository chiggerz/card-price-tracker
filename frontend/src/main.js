import {
  API_BASE_URL,
  fetchCardTypes,
  fetchPlayers,
  fetchSets,
  searchStructured,
} from './api.js';

const bucketConfig = [
  { key: 'exact_matches', label: 'Exact matches' },
  { key: 'same_player_different_number', label: 'Same player, different number' },
  { key: 'same_player_other_variant', label: 'Same player, other variant' },
  { key: 'different_player_same_card_type', label: 'Different player, same card type' },
  { key: 'low_relevance_results', label: 'Low relevance results' },
];

const state = {
  selectedSet: '',
  selectedPlayer: '',
  selectedCardType: '',
  numbering: '',
  players: [],
  cardTypes: [],
};

const elements = {
  setSelect: document.querySelector('#setSelect'),
  playerInput: document.querySelector('#playerInput'),
  playerOptions: document.querySelector('#playerOptions'),
  cardTypeSelect: document.querySelector('#cardTypeSelect'),
  numberingInput: document.querySelector('#numberingInput'),
  searchButton: document.querySelector('#searchButton'),
  formLoading: document.querySelector('#formLoading'),
  formMessage: document.querySelector('#formMessage'),
  resultsSection: document.querySelector('#resultsSection'),
  searchSummary: document.querySelector('#searchSummary'),
  groupedResults: document.querySelector('#groupedResults'),
  backendMessage: document.querySelector('#backendMessage'),
};

function setLoading(text = '') {
  if (!text) {
    elements.formLoading.textContent = '';
    elements.formLoading.classList.add('hidden');
    return;
  }
  elements.formLoading.textContent = text;
  elements.formLoading.classList.remove('hidden');
}

function setFormMessage(message = '', type = 'info') {
  if (!message) {
    elements.formMessage.textContent = '';
    elements.formMessage.className = 'message hidden';
    return;
  }

  elements.formMessage.textContent = message;
  elements.formMessage.className = `message ${type}`;
}

function resetPlayers() {
  state.players = [];
  state.selectedPlayer = '';
  state.selectedCardType = '';
  state.cardTypes = [];

  elements.playerInput.value = '';
  elements.playerInput.disabled = true;
  elements.playerOptions.innerHTML = '';

  resetCardTypes();
}

function resetCardTypes() {
  state.selectedCardType = '';
  state.cardTypes = [];
  elements.cardTypeSelect.innerHTML = '<option value="">Select a card type</option>';
  elements.cardTypeSelect.disabled = true;
}

function updateSearchButtonState() {
  const ready = state.selectedSet && state.selectedPlayer && state.selectedCardType;
  elements.searchButton.disabled = !ready;
}

function renderSets(sets) {
  const options = ['<option value="">Select a set</option>']
    .concat(sets.map((setName) => `<option value="${setName}">${setName}</option>`))
    .join('');
  elements.setSelect.innerHTML = options;
}

function renderPlayers(players) {
  elements.playerOptions.innerHTML = players
    .map((name) => `<option value="${name}"></option>`)
    .join('');
  elements.playerInput.disabled = false;
}

function renderCardTypes(cardTypes) {
  const options = ['<option value="">Select a card type</option>']
    .concat(cardTypes.map((cardType) => `<option value="${cardType}">${cardType}</option>`))
    .join('');
  elements.cardTypeSelect.innerHTML = options;
  elements.cardTypeSelect.disabled = false;
}

function createResultCard(item) {
  const card = document.createElement('article');
  card.className = 'result-card';

  const title = document.createElement('h4');
  title.textContent = item.title || 'Untitled listing';

  const price = document.createElement('p');
  const priceLabel = document.createElement('strong');
  priceLabel.textContent = 'Price: ';
  price.append(priceLabel, document.createTextNode(item.price || 'N/A'));

  const relevance = document.createElement('p');
  const relevanceLabel = document.createElement('strong');
  relevanceLabel.textContent = 'Relevance: ';
  relevance.append(
    relevanceLabel,
    document.createTextNode(Number(item.relevance_score ?? 0).toFixed(2))
  );

  const reason = document.createElement('p');
  const reasonLabel = document.createElement('strong');
  reasonLabel.textContent = 'Reason: ';
  reason.append(reasonLabel, document.createTextNode(item.reason || 'No reason provided.'));

  card.append(title, price, relevance, reason);
  return card;
}

function renderResults(response) {
  const grouped = bucketConfig.map((bucket) => ({
    ...bucket,
    results: response[bucket.key] || [],
  }));
  const total = grouped.reduce((sum, group) => sum + group.results.length, 0);

  elements.resultsSection.classList.remove('hidden');
  elements.searchSummary.innerHTML = `
    <p><strong>Query:</strong> ${response.normalized_query || 'Structured search'}</p>
    <p><strong>Total results:</strong> ${total}</p>
    <p><strong>API base URL:</strong> ${API_BASE_URL}</p>
  `;

  if (response.message) {
    elements.backendMessage.classList.remove('hidden');
    elements.backendMessage.textContent = response.message;
  } else {
    elements.backendMessage.classList.add('hidden');
    elements.backendMessage.textContent = '';
  }

  elements.groupedResults.innerHTML = '';

  if (total === 0) {
    const empty = document.createElement('p');
    empty.className = 'empty-state';
    empty.textContent = 'No results found for this combination yet. Try adjusting the card type or numbering.';
    elements.groupedResults.appendChild(empty);
    return;
  }

  grouped.forEach((group) => {
    const section = document.createElement('section');
    section.className = 'result-group';

    const header = document.createElement('h3');
    header.textContent = `${group.label} (${group.results.length})`;
    section.appendChild(header);

    if (!group.results.length) {
      const empty = document.createElement('p');
      empty.className = 'empty-inline';
      empty.textContent = 'No results in this group.';
      section.appendChild(empty);
    } else {
      const list = document.createElement('div');
      list.className = 'result-grid';
      group.results.forEach((item) => list.appendChild(createResultCard(item)));
      section.appendChild(list);
    }

    elements.groupedResults.appendChild(section);
  });
}

async function loadSets() {
  setLoading('Loading sets...');
  setFormMessage('');
  try {
    const payload = await fetchSets();
    renderSets(payload.sets || []);
    setFormMessage('Select a set to begin.', 'info');
  } catch (error) {
    setFormMessage(`Unable to load sets: ${error.message}`, 'error');
  } finally {
    setLoading('');
  }
}

async function handleSetChange(event) {
  state.selectedSet = event.target.value;
  resetPlayers();
  updateSearchButtonState();

  if (!state.selectedSet) {
    setFormMessage('Select a set to load players.', 'info');
    return;
  }

  setLoading('Loading players...');
  setFormMessage('');

  try {
    const payload = await fetchPlayers(state.selectedSet);
    state.players = payload.players || [];
    renderPlayers(state.players);
    setFormMessage('Now choose a player.', 'info');
  } catch (error) {
    setFormMessage(`Unable to load players: ${error.message}`, 'error');
  } finally {
    setLoading('');
  }
}

async function handlePlayerChange(event) {
  state.selectedPlayer = event.target.value.trim();
  resetCardTypes();
  updateSearchButtonState();

  if (!state.selectedSet || !state.selectedPlayer) {
    return;
  }

  if (!state.players.includes(state.selectedPlayer)) {
    setFormMessage('Please select a player from the suggested list.', 'error');
    return;
  }

  setLoading('Loading card types...');
  setFormMessage('');

  try {
    const payload = await fetchCardTypes(state.selectedSet, state.selectedPlayer);
    state.cardTypes = payload.card_types || [];
    renderCardTypes(state.cardTypes);
    setFormMessage('Choose a card type and optionally add numbering.', 'info');
  } catch (error) {
    setFormMessage(`Unable to load card types: ${error.message}`, 'error');
  } finally {
    setLoading('');
  }
}

function handleCardTypeChange(event) {
  state.selectedCardType = event.target.value;
  updateSearchButtonState();
}

function handleNumberingChange(event) {
  state.numbering = event.target.value.trim();
}

async function handleSearch() {
  setLoading('Searching sold listings...');
  setFormMessage('');

  try {
    const payload = await searchStructured({
      set_name: state.selectedSet,
      player_name: state.selectedPlayer,
      card_type: state.selectedCardType,
      numbering: state.numbering || null,
    });

    renderResults(payload);
    setFormMessage('Search completed.', 'success');
  } catch (error) {
    setFormMessage(`Search failed: ${error.message}`, 'error');
    elements.resultsSection.classList.add('hidden');
  } finally {
    setLoading('');
  }
}

function wireEvents() {
  elements.setSelect.addEventListener('change', handleSetChange);
  elements.playerInput.addEventListener('change', handlePlayerChange);
  elements.cardTypeSelect.addEventListener('change', handleCardTypeChange);
  elements.numberingInput.addEventListener('input', handleNumberingChange);
  elements.searchButton.addEventListener('click', handleSearch);
}

function init() {
  wireEvents();
  loadSets();
}

init();
