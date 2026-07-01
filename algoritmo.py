from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import re

"""
Bias detection algorithm for MindTrade.

Trade dicts are expected to contain (at minimum):
    asset_type, fraction_invested, pnl, direction, trade_reason,
    notes, size, entry_time, exit_time

entry_time / exit_time are strings. HTML5 <input type="datetime-local">
always submits ISO format ("YYYY-MM-DDTHH:MM") regardless of the
displayed locale, so that's the primary format assumed here, with a
couple of fallbacks in case data comes from elsewhere (CSV import, API, etc).
"""

# -------------------
# Helpers
# -------------------

def _text_contains_any(text: str, keywords: List[str]) -> bool:
    text_lower = (text or "").lower()
    return any(k in text_lower for k in keywords)


def _safe_divide(numerator: float, denominator: float) -> float:
    return numerator / denominator if denominator != 0 else 0.0


def _parse_datetime(ts) -> Optional[datetime]:
    """
    Robust-ish datetime parser. Returns None if it can't parse rather than
    raising, so callers can skip/ignore trades with malformed timestamps
    instead of crashing the whole analysis.
    """
    if not ts:
        return None
    if isinstance(ts, datetime):
        return ts

    ts = str(ts).strip()

    formats = [
        "%Y-%m-%dT%H:%M",     # HTML5 datetime-local default (ISO, no seconds)
        "%Y-%m-%dT%H:%M:%S",  # ISO with seconds
        "%Y-%m-%d %H:%M",     # ISO-ish with space instead of T
        "%d/%m/%Y %H:%M",     # dd/mm/yyyy fallback (matches form placeholder text)
    ]
    for fmt in formats:
        try:
            return datetime.strptime(ts, fmt)
        except ValueError:
            continue

    try:
        return datetime.fromisoformat(ts)
    except ValueError:
        return None


def _sort_trades_by_entry(trades: List[Dict]) -> List[Dict]:
    def key(t):
        dt = _parse_datetime(t.get("entry_time"))
        return dt or datetime.min
    return sorted(trades, key=key)


# -------------------
# Bias detectors
# -------------------

def detect_overconfidence(trades: List[Dict]) -> Dict[str, Any]:
    """
    Detect Overconfidence bias based on large position sizing AND trading
    frequency (Barber & Odean-style: overconfident traders trade too much,
    not just too big).
    """
    trades = _sort_trades_by_entry(trades)
    n = len(trades)
    if n == 0:
        return {"bias_detected": False, "confidence_score": 0.0, "explanation": "No trades to analyze."}

    large_trades = sum(1 for t in trades if t.get("fraction_invested", 0) > 0.1)
    freq_large = _safe_divide(large_trades, n)

    entry_times = [_parse_datetime(t.get("entry_time")) for t in trades]
    entry_times = [dt for dt in entry_times if dt is not None]

    score_frequency = 0.0
    if len(entry_times) >= 2:
        span_days = max((max(entry_times) - min(entry_times)).total_seconds() / 86400.0, 1e-6)
        trades_per_day = len(entry_times) / span_days
        # NOTE: 3 trades/day is a placeholder threshold. It should be
        # calibrated against real user data (e.g. a percentile over your
        # beta-tester population) before this number means anything.
        FREQUENCY_THRESHOLD = 3.0
        score_frequency = min(trades_per_day / FREQUENCY_THRESHOLD, 1.0)

    confidence_score = (freq_large + score_frequency) / 2
    bias_detected = confidence_score > 0.3

    parts = []
    if freq_large > 0.3:
        parts.append(f"large position-size trades: {freq_large:.2f}")
    if score_frequency > 0.3:
        parts.append(f"high trading frequency signal: {score_frequency:.2f}")

    explanation = (
        "Indicates possible overestimation of own skill: " + "; ".join(parts) + "."
        if bias_detected else "No strong overconfidence signals detected."
    )

    return {
        "bias_detected": bias_detected,
        "confidence_score": confidence_score,
        "explanation": explanation
    }


def detect_loss_aversion(trades: List[Dict]) -> Dict[str, Any]:
    """
    Detect Loss Aversion (disposition effect) by comparing actual holding
    durations of winning vs losing trades, computed directly from
    entry_time/exit_time — no longer relies on the unused/never-populated
    'sold_early' / 'held_too_long' flags.
    """
    trades = _sort_trades_by_entry(trades)
    n = len(trades)
    if n < 2:
        return {"bias_detected": False, "confidence_score": 0.0, "explanation": "Not enough trades to evaluate."}

    winner_durations = []
    loser_durations = []

    for t in trades:
        entry_dt = _parse_datetime(t.get("entry_time"))
        exit_dt = _parse_datetime(t.get("exit_time"))
        pnl = t.get("pnl", 0)

        if entry_dt is None or exit_dt is None:
            continue  # skip trades with unparseable timestamps

        duration_hours = (exit_dt - entry_dt).total_seconds() / 3600.0
        if duration_hours < 0:
            continue  # malformed data (exit before entry) — skip rather than corrupt the average

        if pnl > 0:
            winner_durations.append(duration_hours)
        elif pnl < 0:
            loser_durations.append(duration_hours)

    if len(winner_durations) < 2 or len(loser_durations) < 2:
        return {
            "bias_detected": False,
            "confidence_score": 0.0,
            "explanation": "Not enough winning/losing trades with valid timestamps to evaluate loss aversion."
        }

    avg_winner_duration = sum(winner_durations) / len(winner_durations)
    avg_loser_duration = sum(loser_durations) / len(loser_durations)

    # Classic disposition-effect proxy: losers held longer than the average winner,
    # winners closed out faster than the average loser.
    held_losers_longer = sum(1 for d in loser_durations if d > avg_winner_duration)
    sold_winners_early = sum(1 for d in winner_durations if d < avg_loser_duration)

    score_hold_losers = _safe_divide(held_losers_longer, len(loser_durations))
    score_sell_winners = _safe_divide(sold_winners_early, len(winner_durations))

    confidence_score = (score_hold_losers + score_sell_winners) / 2
    bias_detected = confidence_score > 0.4

    parts = []
    if score_hold_losers > 0.4:
        parts.append(
            f"losers held ~{avg_loser_duration:.1f}h on average vs {avg_winner_duration:.1f}h for winners "
            f"({score_hold_losers:.2f} of losers held longer than the average winner)"
        )
    if score_sell_winners > 0.4:
        parts.append(f"winners closed earlier than losers on average ({score_sell_winners:.2f})")

    explanation = "; ".join(parts) if parts else "No strong loss aversion detected."

    return {
        "bias_detected": bias_detected,
        "confidence_score": confidence_score,
        "explanation": explanation
    }


def detect_confirmation_bias(trades: List[Dict]) -> Dict[str, Any]:
    """
    Detect Confirmation Bias by checking directional consistency and
    reinforcing language in notes.
    """
    trades = _sort_trades_by_entry(trades)
    n = len(trades)
    if n < 3:
        return {"bias_detected": False, "confidence_score": 0.0, "explanation": "Not enough trades to evaluate reliably."}

    consistent_trades = 0
    reinforcing_notes = 0

    for i in range(1, n):
        dir_prev = trades[i - 1].get("direction", "")
        dir_curr = trades[i].get("direction", "")
        if dir_prev and dir_curr and dir_prev == dir_curr:
            consistent_trades += 1
            note = trades[i].get("notes", "").lower()
            if any(word in note for word in ["confirm", "sure", "believe", "confident"]):
                reinforcing_notes += 1

    score_direction = _safe_divide(consistent_trades, n - 1)
    score_reinforce = _safe_divide(reinforcing_notes, consistent_trades) if consistent_trades else 0.0
    confidence_score = (score_direction + score_reinforce) / 2
    bias_detected = confidence_score > 0.5

    explanation = (
        f"Consistent direction trades: {score_direction:.2f}, reinforcing notes: {score_reinforce:.2f}."
        if bias_detected else "No strong confirmation bias detected."
    )

    return {
        "bias_detected": bias_detected,
        "confidence_score": confidence_score,
        "explanation": explanation
    }


def detect_fomo_bias(trades: List[Dict]) -> Dict[str, Any]:
    """
    Detect FOMO bias via late entries, hype language, risk jumps, reentry
    chasing, and self-labeled reason.
    """
    trades = _sort_trades_by_entry(trades)
    n = len(trades)
    if n == 0:
        return {"bias_detected": False, "confidence_score": 0.0, "explanation": "No trades to analyze."}

    late_keywords = ["breakout", "late", "lagging", "lag"]
    urgent_phrases = [
        "had to get in", "too good to miss", "going parabolic",
        "can't miss", "cannot miss", "everyone's buying", "everybody's buying",
        "hype", "moon", "fomo"
    ]
    reentry_cues = ["missed", "should have", "chase", "chasing", "jumped"]

    late_count = sum(1 for t in trades if _text_contains_any(t.get("notes", ""), late_keywords))
    notes_count = sum(1 for t in trades if _text_contains_any(t.get("notes", ""), urgent_phrases))

    risk_count = 0
    for i in range(1, n):
        prev_frac = trades[i - 1].get("fraction_invested", 0)
        cur_frac = trades[i].get("fraction_invested", 0)
        if prev_frac > 0 and cur_frac / prev_frac > 1.5:
            risk_count += 1

    reentry_count = sum(1 for t in trades if _text_contains_any(t.get("notes", ""), reentry_cues))
    reason_count = sum(1 for t in trades if t.get("trade_reason", "").lower() in {"fomo", "chasing", "trend"})

    score_late = _safe_divide(late_count, n)
    score_notes = _safe_divide(notes_count, n)
    score_risk = _safe_divide(risk_count, max(1, n - 1))
    score_reentry = _safe_divide(reentry_count, n)
    score_reason = _safe_divide(reason_count, n)

    confidence_score = (score_late + score_notes + score_risk + score_reentry + score_reason) / 5
    bias_detected = confidence_score > 0.5

    triggers = []
    if score_late > 0: triggers.append("late entry into strong trend")
    if score_notes > 0: triggers.append("urgent/hype language")
    if score_risk > 0: triggers.append("sudden jump in position size")
    if score_reentry > 0: triggers.append("rapid re-entry after missed move")
    if score_reason > 0: triggers.append("explicit FOMO/chasing reason")

    explanation = "Detected FOMO indicators: " + "; ".join(triggers) + "." if triggers else "No obvious FOMO signals detected."

    return {
        "bias_detected": bias_detected,
        "confidence_score": confidence_score,
        "explanation": explanation
    }


def detect_recency_bias(trades: List[Dict]) -> Dict[str, Any]:
    """
    Detect Recency bias by checking win-stay patterns, loss avoidance, size
    volatility, notes mentioning recent trades, and rapid direction flips.

    NOTE: uses the 'size' field (dollar amount = account_size * fraction_invested),
    which IS populated by app.py — unlike fraction_invested used elsewhere, this
    reflects absolute dollar risk, not the fraction of the account. Keep that in
    mind if you ever compare this score directly against the other detectors.
    """
    trades = _sort_trades_by_entry(trades)
    n = len(trades)
    if n < 2:
        return {"bias_detected": False, "confidence_score": 0.0, "explanation": "Not enough trades to evaluate."}

    win_count = 0
    repeat_count = 0
    loss_count = 0
    avoid_count = 0
    sizes_after_win = []
    sizes_after_loss = []
    flips = 0
    recency_note_count = 0

    recency_pattern = re.compile(r'\b(last time|this time|recent|again)\b', re.I)

    for i in range(n - 1):
        trade = trades[i]
        next_trade = trades[i + 1]
        pnl = trade.get('pnl', 0)
        direction = trade.get('direction', '')
        next_direction = next_trade.get('direction', '')
        size = trade.get('size', 0)
        next_size = next_trade.get('size', 0)
        notes = trade.get('notes', '')

        if pnl > 0:
            win_count += 1
            if direction and next_direction == direction:
                repeat_count += 1
            sizes_after_win.append(next_size)

        if pnl < 0:
            loss_count += 1
            if (next_direction and next_direction != direction) or (next_size < size):
                avoid_count += 1
            sizes_after_loss.append(next_size)

        if next_direction and direction and next_direction != direction:
            flips += 1

        if notes and recency_pattern.search(notes):
            recency_note_count += 1

    score_repeat_winner = _safe_divide(repeat_count, win_count) if win_count > 0 else 0.0
    score_avoid_loss = _safe_divide(avoid_count, loss_count) if loss_count > 0 else 0.0

    mean_win = sum(sizes_after_win) / len(sizes_after_win) if sizes_after_win else 0
    mean_loss = sum(sizes_after_loss) / len(sizes_after_loss) if sizes_after_loss else 0
    if mean_win > mean_loss and mean_win > 0:
        score_volatility = min((mean_win - mean_loss) / mean_win, 1.0)
    else:
        score_volatility = 0.0

    score_short_term_loop = flips / (n - 1)
    score_notes = recency_note_count / n

    weights = {
        'repeat_winner': 0.25,
        'avoid_loss': 0.25,
        'volatility': 0.25,
        'notes': 0.125,
        'short_loop': 0.125
    }

    confidence = (
        weights['repeat_winner'] * score_repeat_winner +
        weights['avoid_loss'] * score_avoid_loss +
        weights['volatility'] * score_volatility +
        weights['notes'] * score_notes +
        weights['short_loop'] * score_short_term_loop
    )
    confidence = max(0.0, min(confidence, 1.0))
    detected = confidence > 0.5

    reasons = []
    if score_repeat_winner > 0.5:
        reasons.append("repeating winners (win-stay)")
    if score_avoid_loss > 0.5:
        reasons.append("cutting/reversing after losses")
    if score_volatility > 0.5:
        reasons.append("larger bets after wins (house-money effect)")
    if score_notes > 0.5:
        reasons.append("notes citing recent trades")
    if score_short_term_loop > 0.5:
        reasons.append("rapid direction flips")

    explanation = "; ".join(reasons) if reasons else "no strong recency signals"

    return {
        "bias_detected": detected,
        "confidence_score": confidence,
        "explanation": explanation
    }


def detect_revenge_trading(trades: List[Dict]) -> Dict[str, Any]:
    """
    Detect Revenge Trading by checking if traders increase position size or
    risk after losses and if notes reflect emotional language.
    """
    trades = _sort_trades_by_entry(trades)
    n = len(trades)
    if n < 2:
        return {"bias_detected": False, "confidence_score": 0.0, "explanation": "Not enough trades to evaluate."}

    emotional_keywords = ["revenge", "angry", "frustrated", "rage", "upset", "mad"]
    revenge_increase_count = 0
    emotional_notes_count = 0
    loss_following_trades = 0

    for i in range(1, n):
        prev_pnl = trades[i - 1].get("pnl", 0)
        cur_frac = trades[i].get("fraction_invested", 0)
        prev_frac = trades[i - 1].get("fraction_invested", 0)

        if prev_pnl < 0:
            loss_following_trades += 1
            if cur_frac > prev_frac:
                revenge_increase_count += 1

        if _text_contains_any(trades[i].get("notes", ""), emotional_keywords):
            emotional_notes_count += 1

    score_revenge_risk = _safe_divide(revenge_increase_count, loss_following_trades) if loss_following_trades > 0 else 0.0
    score_emotional_notes = emotional_notes_count / n

    confidence_score = (score_revenge_risk + score_emotional_notes) / 2
    bias_detected = confidence_score > 0.4

    parts = []
    if score_revenge_risk > 0.4:
        parts.append(f"increased position size after losses ({score_revenge_risk:.2f})")
    if score_emotional_notes > 0.2:
        parts.append(f"emotional language in notes ({score_emotional_notes:.2f})")

    explanation = "; ".join(parts) if parts else "No strong revenge trading detected."

    return {
        "bias_detected": bias_detected,
        "confidence_score": confidence_score,
        "explanation": explanation
    }


def detect_herd_behavior(trades: List[Dict], peer_trades: List[Dict] = None) -> Dict[str, Any]:
    """
    Detect Herd Behavior by checking if the trader's activity follows
    popular/hyped assets or, if peer_trades is provided, mimics the peer
    group's direction within a real time window (was previously comparing
    Python hash() values of timestamp strings, which is meaningless).
    """
    trades = _sort_trades_by_entry(trades)
    n = len(trades)
    if n == 0:
        return {"bias_detected": False, "confidence_score": 0.0, "explanation": "No trades to analyze."}

    popular_assets = {"crypto", "meme", "hot", "trending"}
    herd_notes_cues = ["everyone's buying", "following crowd", "herd", "everyone is in", "popular", "social proof"]

    herd_asset_count = sum(1 for t in trades if any(pa in t.get("asset_type", "").lower() for pa in popular_assets))
    herd_notes_count = sum(1 for t in trades if _text_contains_any(t.get("notes", ""), herd_notes_cues))

    score_asset = _safe_divide(herd_asset_count, n)
    score_notes = _safe_divide(herd_notes_count, n)

    score_peer_follow = 0.0
    if peer_trades:
        PEER_WINDOW = timedelta(hours=24)  # "same day-ish" window — tune based on your asset classes
        peer_trades_sorted = _sort_trades_by_entry(peer_trades)

        match_count = 0
        comparable_count = 0

        for t in trades:
            t_time = _parse_datetime(t.get("entry_time"))
            t_asset = t.get("asset_type", "").lower()
            t_direction = t.get("direction", "")

            if t_time is None:
                continue

            peer_same_asset = [
                p for p in peer_trades_sorted
                if p.get("asset_type", "").lower() == t_asset
                and _parse_datetime(p.get("entry_time")) is not None
                and abs(_parse_datetime(p.get("entry_time")) - t_time) <= PEER_WINDOW
            ]

            directions = [p.get("direction", "") for p in peer_same_asset if p.get("direction", "")]
            if directions:
                comparable_count += 1
                majority_dir = max(set(directions), key=directions.count)
                if majority_dir == t_direction:
                    match_count += 1

        # Divide by trades that actually HAD comparable peer data, not by n,
        # so trades with no peer activity in the window don't dilute the score.
        score_peer_follow = _safe_divide(match_count, comparable_count)

    weights = {'asset': 0.4, 'notes': 0.3, 'peer': 0.3}
    confidence_score = (weights['asset'] * score_asset +
                         weights['notes'] * score_notes +
                         weights['peer'] * score_peer_follow)

    bias_detected = confidence_score > 0.5

    triggers = []
    if score_asset > 0: triggers.append("trades on popular/hyped assets")
    if score_notes > 0: triggers.append("notes mentioning herd or crowd")
    if score_peer_follow > 0: triggers.append("mimicking peer group trades")

    explanation = "Detected herd behavior indicators: " + "; ".join(triggers) + "." if triggers else "No strong herd behavior signals detected."

    return {
        "bias_detected": bias_detected,
        "confidence_score": confidence_score,
        "explanation": explanation
    }


def detect_all_biases(trades: List[Dict], peer_trades: List[Dict] = None) -> Dict[str, Any]:
    """
    Run all bias detection functions on the trades.
    peer_trades is optional and used only for herd behavior detection.
    """
    results = {
        'Overconfidence': detect_overconfidence(trades),
        'Loss Aversion': detect_loss_aversion(trades),
        'Confirmation Bias': detect_confirmation_bias(trades),
        'FOMO': detect_fomo_bias(trades),
        'Recency Bias': detect_recency_bias(trades),
        'Revenge Trading': detect_revenge_trading(trades),
        'Herd Behavior': detect_herd_behavior(trades, peer_trades),
    }

    total_confidence = sum(bias['confidence_score'] for bias in results.values())
    overall_confidence = _safe_divide(total_confidence, len(results))
    detected_biases = [name for name, bias in results.items() if bias['bias_detected']]

    return {
        "detected_biases": detected_biases,
        "overall_confidence": overall_confidence,
        "details": results
    }

# Example usage:
# trades = [ {...}, {...} ]  # list of trade dicts with keys like 'pnl', 'direction', 'fraction_invested', 'notes', etc.
# peer_trades = [ {...}, {...} ]  # optional, for herd behavior
# report = detect_all_biases(trades, peer_trades)
# print(report)
