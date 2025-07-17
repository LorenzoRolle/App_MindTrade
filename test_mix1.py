from datetime import datetime
from textblob import TextBlob

# --- Constants ---
LAMBDA = 2.0  # Loss aversion weight (not used directly here but useful if extended)
OVERCONFIDENCE_THRESHOLD = 0.05  # >5% of account invested signals risk

# --- Helper functions ---
def compute_position_size(account_size, fraction_invested, entry_price):
    return (account_size * fraction_invested) / entry_price

def get_trade_input():
    entry_time_str = input("Entry date & time (YYYY-MM-DD HH:MM): ").strip()
    exit_time_str  = input("Exit  date & time (YYYY-MM-DD HH:MM): ").strip()
    entry_price    = float(input("Entry price: "))
    exit_price     = float(input("Exit  price: "))
    account_size   = float(input("Total account size: "))
    fraction       = float(input("Fraction of account used (0–1): "))
    note           = input("Trader note / explanation: ")

    # Auto-fill missing time with "00:00"
    if len(entry_time_str) == 10:
        entry_time_str += " 00:00"
    if len(exit_time_str) == 10:
        exit_time_str += " 00:00"

    entry_time = datetime.strptime(entry_time_str, "%Y-%m-%d %H:%M")
    exit_time  = datetime.strptime(exit_time_str, "%Y-%m-%d %H:%M")
    position_size = compute_position_size(account_size, fraction, entry_price)
    pnl = (exit_price - entry_price) * position_size
    hold_hrs = (exit_time - entry_time).total_seconds() / 3600
    sentiment = TextBlob(note).sentiment.polarity

    return {
        'entry_price': entry_price,
        'exit_price': exit_price,
        'account_size': account_size,
        'fraction': fraction,
        'entry_time': entry_time,
        'exit_time': exit_time,
        'position_size': position_size,
        'pnl': pnl,
        'duration': hold_hrs,
        'sentiment': sentiment,
        'note': note
    }

# --- Bias Analysis ---
def analyze_overconfidence(trade):
    score = 0
    messages = []

    # Risk exposure check
    if trade['fraction'] > OVERCONFIDENCE_THRESHOLD:
        score += 0.5
        messages.append(f"⚠️ High risk exposure: {trade['fraction']*100:.1f}% of account used.")

    # Positive sentiment check
    if trade['sentiment'] > 0.4:
        score += 0.3
        messages.append("🗣️ Strong positive sentiment in notes.")

    # Keywords for overconfidence
    keywords = ['sure', 'confident', 'guaranteed', 'easy', 'certain', 'obvious', 'no way', 'all in']
    if any(word in trade['note'].lower() for word in keywords):
        score += 0.2
        messages.append("🧠 Confidence keywords detected in notes.")

    score = min(1.0, score)
    return score, messages

def analyze_loss_aversion(trades):
    losers = [t for t in trades if t['pnl'] < 0]
    winners = [t for t in trades if t['pnl'] > 0]
    if len(trades) < 2 or not winners:
        return None, "⚠️ Need at least 2 trades and one winning trade for Loss Aversion analysis."

    avg_loss_dur = sum(t['duration'] for t in losers) / len(losers)
    avg_win_dur  = sum(t['duration'] for t in winners) / len(winners)
    avg_neg_sent = abs(min(0, sum(t['sentiment'] for t in losers) / len(losers)))

    # Loss aversion keywords boost
    keywords = ['held', 'afraid', 'recover', 'bounce', 'waited', 'hope', 'hesitate', 'panic', 'loss']
    note_boost = 0.0
    for t in losers:
        note_boost += sum(1 for word in keywords if word in t['note'].lower())
    note_boost = min(note_boost * 0.05, 0.2)

    score = min(1.0, (avg_loss_dur / avg_win_dur) * 0.6 + avg_neg_sent * 0.4 + note_boost)
    return score, {
        'avg_loss_dur': avg_loss_dur,
        'avg_win_dur': avg_win_dur,
        'avg_neg_sent': avg_neg_sent,
        'keyword_boost': note_boost
    }

# --- Main program ---
def main():
    print("🔍 MINDTRADE BIAS DETECTOR 🔍")
    trades = []
    n = int(input("How many trades do you want to input? "))
    for i in range(n):
        print(f"\n📥 Trade {i+1}")
        trades.append(get_trade_input())

    print("\n📊 OVERCONFIDENCE ANALYSIS")
    for i, t in enumerate(trades):
        score, messages = analyze_overconfidence(t)
        print(f"\nTrade {i+1} Overconfidence Score: {round(score,2)}")
        for msg in messages:
            print(" -", msg)

    print("\n📉 LOSS AVERSION ANALYSIS")
    la_score, la_result = analyze_loss_aversion(trades)
    if la_score is None:
        print(la_result)
    else:
        print(f"Loss Aversion Score: {round(la_score,2)}")
        print(f" - Avg losing trade duration: {la_result['avg_loss_dur']:.2f} hrs")
        print(f" - Avg winning trade duration: {la_result['avg_win_dur']:.2f} hrs")
        print(f" - Avg negative sentiment: {la_result['avg_neg_sent']:.2f}")
        print(f" - Keyword boost: {la_result['keyword_boost']:.2f}")

if __name__ == "__main__":
    main()
