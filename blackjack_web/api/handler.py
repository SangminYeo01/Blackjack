from flask import Flask, request, jsonify, session
import os
import random
import google.generativeai as genai
from dotenv import load_dotenv

# Flask 앱 초기화 및 시크릿 키 설정
app = Flask(__name__)
app.secret_key = os.urandom(24)

# .env 파일 로드 및 Gemini API 설정
load_dotenv()
try:
    genai.configure(api_key=os.environ["GEMINI_API_KEY"])
    gemini = genai.GenerativeModel('gemini-pro')
except KeyError:
    # Vercel 배포 환경에서는 .env가 아닌 환경 변수를 직접 사용
    if "GEMINI_API_KEY" in os.environ:
        genai.configure(api_key=os.environ["GEMINI_API_KEY"])
        gemini = genai.GenerativeModel('gemini-pro')
    else:
        # 로컬, 배포 환경 모두에 키가 없는 경우
        print("GEMINI_API_KEY가 설정되지 않았습니다.")
        gemini = None

# --- 카드 및 덱 클래스 (기존 로직과 유사) ---
class Card:
    def __init__(self, suit, rank):
        self.suit = suit
        self.rank = rank
        self.value = self._get_value()

    def _get_value(self):
        if self.rank in ['J', 'Q', 'K']: return 10
        elif self.rank == 'A': return 11
        else: return int(self.rank)
    
    def to_dict(self):
        return {'suit': self.suit, 'rank': self.rank}

class Deck:
    def __init__(self):
        self.cards = []
        suits = ['♠', '♥', '♦', '♣']
        ranks = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A']
        for suit in suits:
            for rank in ranks:
                self.cards.append(Card(suit, rank))
    
    def shuffle(self):
        random.shuffle(self.cards)

    def deal(self):
        return self.cards.pop() if self.cards else None

# --- 헬퍼 함수 ---
def get_hand_value(hand):
    value = sum(card.value for card in hand)
    aces = sum(1 for card in hand if card.rank == 'A')
    while value > 21 and aces:
        value -= 10
        aces -= 1
    return value

def get_game_state(game_over=False, message=""):
    player_hand = [card.to_dict() for card in session['player_hand']]
    dealer_hand = [card.to_dict() for card in session['dealer_hand']]
    
    state = {
        'player_hand': player_hand,
        'dealer_hand': dealer_hand,
        'player_score': get_hand_value(session['player_hand']),
        'dealer_score': get_hand_value(session['dealer_hand']),
        'player_money': session['player_money'],
        'game_over': game_over,
        'message': message,
        'hide_dealer_card': not game_over
    }
    
    if game_over:
        state['dealer_score'] = get_hand_value(session['dealer_hand'])
    else:
        # 게임 중일 때 딜러의 첫 카드 점수만 보여줌
        state['dealer_score'] = session['dealer_hand'][0].value if session['dealer_hand'] else 0

    return state

def get_dealer_action_from_gemini(player_hand, dealer_hand):
    if not gemini:
        # Gemini API가 설정되지 않은 경우 기본 규칙 사용
        return "HIT" if get_hand_value(dealer_hand) < 17 else "STAND"
        
    player_score = get_hand_value(player_hand)
    dealer_score = get_hand_value(dealer_hand)
    player_hand_str = ", ".join(f"{c.rank}{c.suit}" for c in player_hand)
    dealer_hand_str = ", ".join(f"{c.rank}{c.suit}" for c in dealer_hand)

    prompt = f"""
    당신은 블랙잭 게임의 딜러입니다. 당신의 역할은 플레이어를 이기는 것입니다.
    카지노 딜러처럼 행동해주세요. 약간의 유머와 함께 자신감 있는 태도를 보여주세요.
    결정은 'HIT' 또는 'STAND' 두 가지 중 하나로만 내려야 합니다. 다른 말은 하지 마세요.

    현재 상황:
    - 당신의 카드: {dealer_hand_str} (점수: {dealer_score})
    - 플레이어의 카드: {player_hand_str} (점수: {player_score})

    규칙:
    - 당신의 점수가 16 이하면 무조건 'HIT'해야 합니다.
    - 당신의 점수가 플레이어 점수보다 낮으면 'HIT'를 고려해야 합니다.
    - 당신의 점수가 21에 가까우면 'STAND'하는 것이 현명합니다.

    이제 결정을 내리세요. HIT 또는 STAND?
    """
    try:
        response = gemini.generate_content(prompt)
        decision = response.text.strip().upper()
        if "HIT" in decision:
            return "HIT"
        return "STAND"
    except Exception as e:
        print(f"Gemini API 호출 오류: {e}")
        return "HIT" if get_hand_value(dealer_hand) < 17 else "STAND"

# --- API 라우트 ---
@app.route('/api/handler', methods=['POST'])
def handler():
    data = request.get_json()
    action = data.get('action')

    if action == 'start_game':
        deck = Deck()
        deck.shuffle()
        session['deck'] = [c.to_dict() for c in deck.cards] # 세션 저장을 위해 직렬화
        session['player_hand'] = [Card(**deck.deal().to_dict()), Card(**deck.deal().to_dict())]
        session['dealer_hand'] = [Card(**deck.deal().to_dict()), Card(**deck.deal().to_dict())]

        if 'player_money' not in session:
            session['player_money'] = 1000
        
        session['current_bet'] = data.get('bet', 10)
        session['player_money'] -= session['current_bet']

        player_score = get_hand_value(session['player_hand'])
        if player_score == 21:
            return jsonify(get_game_state(game_over=True, message="블랙잭! 플레이어 승리!"))
        
        return jsonify(get_game_state())

    # --- 카드, 덱, 손패를 세션에서 재구성 ---
    deck_from_session = [Card(**c) for c in session.get('deck', [])]
    player_hand_from_session = [Card(**c) for c in session.get('player_hand', [])]
    dealer_hand_from_session = [Card(**c) for c in session.get('dealer_hand', [])]
    session['player_hand'] = player_hand_from_session
    session['dealer_hand'] = dealer_hand_from_session

    if action == 'hit':
        session['player_hand'].append(deck_from_session.pop())
        session['deck'] = [c.to_dict() for c in deck_from_session] # 세션 업데이트

        if get_hand_value(session['player_hand']) > 21:
            return jsonify(get_game_state(game_over=True, message="플레이어 버스트! 딜러 승리."))
        return jsonify(get_game_state())

    if action == 'stand':
        # 딜러 턴 로직
        while get_hand_value(session['dealer_hand']) < 21:
            action = get_dealer_action_from_gemini(session['player_hand'], session['dealer_hand'])
            if action == 'STAND':
                break
            
            new_card = deck_from_session.pop()
            if new_card:
                session['dealer_hand'].append(new_card)
            else: # 덱에 카드가 없으면 중단
                break
        
        session['deck'] = [c.to_dict() for c in deck_from_session]

        player_score = get_hand_value(session['player_hand'])
        dealer_score = get_hand_value(session['dealer_hand'])

        if dealer_score > 21 or player_score > dealer_score:
            session['player_money'] += session['current_bet'] * 2
            message = "딜러 버스트! 플레이어 승리." if dealer_score > 21 else "플레이어 승리!"
        elif dealer_score > player_score:
            message = "딜러 승리!"
        else:
            session['player_money'] += session['current_bet']
            message = "무승부!"
            
        return jsonify(get_game_state(game_over=True, message=message))

    return jsonify({'error': 'Unknown action'}), 400 