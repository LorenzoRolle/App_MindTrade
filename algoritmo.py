from typing import List, Dict, Any
import re

"""
to be explained (all)s
"""

def _text_contains_any(text: str, keywords: List[str]) -> bool:
    text_lower = text.lower()
    return any(k in text_lower for k in keywords)

def _safe_divide(numerator: float, denominator: float) -> float:
    return numerator / denominator if denominator != 0 else 0.0

def _sort_trades_by_entry(trades: List[Dict]) -> List[Dict]:
    return sorted(trades, key=lambda t: t.get("entry_time", ""))

def detect_overconfidence(trades: List[Dict]) -> Dict[str, Any]:
    """
    Detect Overconfidence bias based on large trade sizes and excessive trading.
    """
    trades = _sort_trades_by_entry(trades)
    n = len(trades)
    if n == 0:
        return {"bias_detected": False, "confidence_score": 0.0, "explanation": "No trades to analyze."}

    # Overconfidence heuristic: frequent large fraction_invested trades (e.g., >10%)
    large_trades = sum(1 for t in trades if t.get("fraction_invested", 0) > 0.1)
    freq_large = _safe_divide(large_trades, n)

    # Excessive trading heuristic: trades per time unit (assuming timestamps)
    # For simplicity, check if average time between trades is very short
    times = [t.get("entry_time") for t in trades]
    # Skip if timestamps missing or invalid
    # This is a rough heuristic, so omitted for now

    confidence_score = freq_large  # simple proxy for demo
    bias_detected = confidence_score > 0.3

    explanation = (
        f"High fraction invested trades: {freq_large:.2f}. "
        "Indicates tendency to overestimate own skill and take large risks."
    ) if bias_detected else "No strong overconfidence signals detected."

    return {
        "bias_detected": bias_detected,
        "confidence_score": confidence_score,
        "explanation": explanation
    }

def detect_loss_aversion(trades: List[Dict]) -> Dict[str, Any]:
    """
    Detect Loss Aversion bias by checking holding onto losers and selling winners prematurely.
    """
    trades = _sort_trades_by_entry(trades)
    n = len(trades)
    if n < 2:
        return {"bias_detected": False, "confidence_score": 0.0, "explanation": "Not enough trades to evaluate."}

    sell_winners = 0
    hold_losers = 0
    winners = 0
    losers = 0

    for t in trades:
        pnl = t.get("pnl", 0)
        if pnl > 0:
            winners += 1
            if t.get("sold_early", False):  # hypothetical flag from notes or data
                sell_winners += 1
        elif pnl < 0:
            losers += 1
            if t.get("held_too_long", False):
                hold_losers += 1

    score_sell_winners = _safe_divide(sell_winners, winners)
    score_hold_losers = _safe_divide(hold_losers, losers)
    confidence_score = (score_sell_winners + score_hold_losers) / 2
    bias_detected = confidence_score > 0.4

    explanation_parts = []
    if score_sell_winners > 0.4:
        explanation_parts.append(f"Prematurely sold winners ({score_sell_winners:.2f})")
    if score_hold_losers > 0.4:
        explanation_parts.append(f"Held losers too long ({score_hold_losers:.2f})")
    explanation = "; ".join(explanation_parts) if explanation_parts else "No strong loss aversion detected."

    return {
        "bias_detected": bias_detected,
        "confidence_score": confidence_score,
        "explanation": explanation
    }

def detect_confirmation_bias(trades: List[Dict]) -> Dict[str, Any]:
    """
    Detect Confirmation Bias by checking directional consistency and reinforcing notes.
    """
    trades = _sort_trades_by_entry(trades)
    n = len(trades)
    if n == 0:
        return {"bias_detected": False, "confidence_score": 0.0, "explanation": "No trades to analyze."}

    directional_consistency = 0
    reinforcing_notes = 0
    consistent_trades = 0

    for i in range(1, n):
        dir_prev = trades[i-1].get("direction", "")
        dir_curr = trades[i].get("direction", "")
        if dir_prev and dir_curr and dir_prev == dir_curr:
            consistent_trades += 1
            note = trades[i].get("notes", "").lower()
            if any(word in note for word in ["confirm", "sure", "believe", "confident"]):
                reinforcing_notes += 1

    score_direction = _safe_divide(consistent_trades, n-1)
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
    Detect FOMO bias via late entries, hype language, risk jumps, reentry chasing, and self-label.
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
        prev_frac = trades[i-1].get("fraction_invested", 0)
        cur_frac = trades[i].get("fraction_invested", 0)
        if prev_frac > 0 and cur_frac / prev_frac > 1.5:
            risk_count += 1

    reentry_count = sum(1 for t in trades if _text_contains_any(t.get("notes", ""), reentry_cues))
    reason_count = sum(1 for t in trades if t.get("trade_reason", "").lower() in {"fomo", "chasing", "trend"})

    score_late = _safe_divide(late_count, n)
    score_notes = _safe_divide(notes_count, n)
    score_risk = _safe_divide(risk_count, max(1, n-1))
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
    Detect Recency bias by checking win-stay patterns, loss avoidance, size volatility,
    notes mentioning recent trades, and rapid direction flips.
    """
    import re

    trades = _sort_trades_by_entry(trades)
    n = len(trades)
    if n < 2:
        return {"detected": False, "confidence_score": 0.0, "explanation": "Not enough trades to evaluate."}

    win_count = 0
    repeat_count = 0
    loss_count = 0
    avoid_count = 0
    sizes_after_win = []
    sizes_after_loss = []
    flips = 0
    recency_note_count = 0

    recency_pattern = re.compile(r'\b(last time|this time|recent|again)\b', re.I)

    for i in range(n-1):
        trade = trades[i]
        next_trade = trades[i+1]
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

    mean_win = sum(sizes_after_win)/len(sizes_after_win) if sizes_after_win else 0
    mean_loss = sum(sizes_after_loss)/len(sizes_after_loss) if sizes_after_loss else 0
    if mean_win > mean_loss and mean_win > 0:
        score_volatility = min((mean_win - mean_loss) / mean_win, 1.0)
    else:
        score_volatility = 0.0

    score_short_term_loop = flips / (n-1)
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
    Detect Revenge Trading by checking if traders increase position size or risk after losses
    and if notes reflect emotional language such as 'revenge', 'angry', 'frustrated'.
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
        prev_pnl = trades[i-1].get("pnl", 0)
        cur_frac = trades[i].get("fraction_invested", 0)
        prev_frac = trades[i-1].get("fraction_invested", 0)

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

    explanation_parts = []
    if score_revenge_risk > 0.4:
        explanation_parts.append(f"Increased position size after losses ({score_revenge_risk:.2f})")
    if score_emotional_notes > 0.2:
        explanation_parts.append(f"Emotional language in notes ({score_emotional_notes:.2f})")

    explanation = "; ".join(explanation_parts) if explanation_parts else "No strong revenge trading detected."

    return {
        "bias_detected": bias_detected,
        "confidence_score": confidence_score,
        "explanation": explanation
    }

def detect_herd_behavior(trades: List[Dict], peer_trades: List[Dict] = None) -> Dict[str, Any]:
    """
    Detect Herd Behavior by checking if trader’s trades closely follow peer group behavior or popular assets.
    If peer_trades is provided, compare directions and timing for mimicry.
    """
    trades = _sort_trades_by_entry(trades)
    n = len(trades)
    if n == 0:
        return {"bias_detected": False, "confidence_score": 0.0, "explanation": "No trades to analyze."}

    # Simple proxy: count trades on popular/hyped assets or with notes indicating following others
    popular_assets = {"crypto", "meme", "hot", "trending"}
    herd_notes_cues = ["everyone's buying", "following crowd", "herd", "everyone is in", "popular", "social proof"]

    herd_asset_count = 0
    herd_notes_count = 0

    for t in trades:
        asset = t.get("asset_type", "").lower()
        notes = t.get("notes", "").lower()
        if any(pa in asset for pa in popular_assets):
            herd_asset_count += 1
        if any(cue in notes for cue in herd_notes_cues):
            herd_notes_count += 1

    score_asset = _safe_divide(herd_asset_count, n)
    score_notes = _safe_divide(herd_notes_count, n)

    # Optional peer comparison (if peer_trades provided)
    score_peer_follow = 0.0
    if peer_trades:
        # Count fraction of trades matching majority peer direction on same asset within time window
        peer_trades_sorted = _sort_trades_by_entry(peer_trades)
        match_count = 0
        for t in trades:
            t_time = t.get("entry_time")
            t_asset = t.get("asset_type", "").lower()
            t_direction = t.get("direction", "")
            # Find peer trades in same asset, within short time window (e.g. same day)
            peer_same_asset = [p for p in peer_trades_sorted if p.get("asset_type", "").lower() == t_asset and abs(hash(p.get("entry_time", "")) - hash(t_time)) < 100000]
            # Count majority peer direction
            directions = [p.get("direction", "") for p in peer_same_asset if p.get("direction", "")]
            if directions:
                majority_dir = max(set(directions), key=directions.count)
                if majority_dir == t_direction:
                    match_count += 1
        score_peer_follow = _safe_divide(match_count, n)

    # Combine with weights
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
    Return a dictionary summarizing all bias scores and explanations.
    peer_trades is optional and used only for herd behavior detection.
    """
    results = {}

    results['Overconfidence'] = detect_overconfidence(trades)
    results['Loss Aversion'] = detect_loss_aversion(trades)
    results['Confirmation Bias'] = detect_confirmation_bias(trades)
    results['FOMO'] = detect_fomo_bias(trades)
    results['Recency Bias'] = detect_recency_bias(trades)
    results['Revenge Trading'] = detect_revenge_trading(trades)
    results['Herd Behavior'] = detect_herd_behavior(trades, peer_trades)

    # Compute overall confidence as average of detected biases (or weighted if desired)
    total_confidence = sum(bias['confidence_score'] for bias in results.values())
    overall_confidence = _safe_divide(total_confidence, len(results))

    detected_biases = [name for name, bias in results.items() if bias['bias_detected']]

    summary = {
        "detected_biases": detected_biases,
        "overall_confidence": overall_confidence,
        "details": results
    }
    return summary

# Example usage:
# trades = [ {...}, {...} ]  # list of trade dicts with keys like 'pnl', 'direction', 'fraction_invested', 'notes', etc.
# peer_trades = [ {...}, {...} ]  # optional, for herd behavior
# report = detect_all_biases(trades, peer_trades)
# print(report)
