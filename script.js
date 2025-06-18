// DOM Elements
const playerMoneyEl = document.getElementById('player-money');
const dealerScoreEl = document.getElementById('dealer-score');
const playerScoreEl = document.getElementById('player-score');
const dealerCardsEl = document.getElementById('dealer-cards');
const playerCardsEl = document.getElementById('player-cards');
const messageEl = document.getElementById('message');
const betAmountInput = document.getElementById('bet-amount');
const betButton = document.getElementById('bet-button');
const hitButton = document.getElementById('hit-button');
const standButton = document.getElementById('stand-button');

// API Endpoint
const API_URL = '/api/handler';

// Game state
let playerMoney = 1000;
let currentBet = 0;

// Event Listeners
betButton.addEventListener('click', placeBet);
hitButton.addEventListener('click', () => handlePlayerAction('hit'));
standButton.addEventListener('click', () => handlePlayerAction('stand'));

async function placeBet() {
    const betAmount = parseInt(betAmountInput.value);
    if (isNaN(betAmount) || betAmount <= 0 || betAmount > playerMoney) {
        showMessage("유효한 금액을 베팅하세요.");
        return;
    }
    
    currentBet = betAmount;
    playerMoney -= currentBet;
    updateMoneyDisplay();
    
    setControls(true);
    showMessage("");
    
    const response = await fetch(API_URL, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action: 'start_game', bet: currentBet })
    });
    const gameState = await response.json();
    updateUI(gameState);

    if (gameState.player_blackjack) {
        handlePlayerAction('stand');
    }
}

async function handlePlayerAction(action) {
    const response = await fetch(API_URL, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action: action })
    });
    const gameState = await response.json();
    updateUI(gameState);

    if (gameState.game_over) {
        endRound(gameState);
    }
}

function updateUI(state) {
    // Render cards
    renderCards(dealerCardsEl, state.dealer_hand, state.hide_dealer_card);
    renderCards(playerCardsEl, state.player_hand, false);
    
    // Update scores
    dealerScoreEl.textContent = state.dealer_score;
    playerScoreEl.textContent = state.player_score;
    
    // Show messages
    if (state.message) {
        showMessage(state.message);
    }
}

function renderCards(element, hand, hideFirstCard) {
    element.innerHTML = '';
    hand.forEach((card, index) => {
        const cardEl = document.createElement('div');
        cardEl.classList.add('card');

        if (index === 0 && hideFirstCard) {
            cardEl.classList.add('back');
        } else {
            const suit = card.suit;
            const rank = card.rank;
            cardEl.innerHTML = `<span>${rank}</span><span class="suit">${suit}</span>`;
            if (suit === '♥' || suit === '♦') {
                cardEl.classList.add('red');
            }
        }
        element.appendChild(cardEl);
    });
}

function endRound(state) {
    playerMoney = state.player_money;
    updateMoneyDisplay();
    setControls(false);

    if (playerMoney <= 0) {
        showMessage("자금을 모두 잃었습니다! 게임 오버.");
        betButton.disabled = true;
        betAmountInput.disabled = true;
    }
}

function showMessage(msg) {
    messageEl.textContent = msg;
}

function updateMoneyDisplay() {
    playerMoneyEl.textContent = playerMoney;
}

function setControls(inGame) {
    hitButton.disabled = !inGame;
    standButton.disabled = !inGame;
    betButton.disabled = inGame;
    betAmountInput.disabled = inGame;
} 