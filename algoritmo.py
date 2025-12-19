from typing import List, Dict, Any
import re
from datetime import datetime

def _text_contains_any(text: str, keywords: List[str]) -> bool:
    """Check if text contains any of the keywords."""
    if not text:
        return False
    text_lower = text.lower()
    return any(k in text_lower for k in keywords)

def _safe_divide(numerator: float, denominator: float) -> float:
    """Safe division with zero denominator handling."""
    return numerator / denominator if denominator != 0 else 0.0

def _calculate_pnl(trade: Dict) -> float:
    """Calculate P&L from trade data."""
    entry = trade.get("entry_price", 0)
    exit_price = trade.get("exit_price", 0)
    account = trade.get("account_size", 0)
    fraction = trade.get("fraction_invested", 0)
    direction = trade.get("direction", "").lower()
    
    if not all([entry, exit_price, account, fraction, direction]):
        return 0.0
    
    invested = account * fraction
    if direction == "long":
        return (exit_price - entry) / entry * invested
    elif direction == "short":
        return (entry - exit_price) / entry * invested
    return 0.0

def _parse_timestamp(timestamp_str: str) -> datetime:
    """Parse timestamp string to datetime object."""
    try:
        # Support multiple formats
        formats = ["%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"]
        for fmt in formats:
            try:
                return datetime.strptime(timestamp_str, fmt)
            except ValueError:
                continue
        return datetime.min
    except:
        return datetime.min

def _sort_trades_by_entry(trades: List[Dict]) -> List[Dict]:
    """Sort trades by entry timestamp."""
    def get_time(trade):
        ts = trade.get("entry_timestamp", trade.get("entry_time", ""))
        return _parse_timestamp(ts)
    
    return sorted(trades, key=get_time)

def detect_overconfidence(trades: List[Dict]) -> Dict[str, Any]:
    """
    Detect Overconfidence bias based on large trade sizes.
    """
    trades = _sort_trades_by_entry(trades)
    n = len(trades)
    if n == 0:
        return {"bias_detected": False, "confidence_score": 0.0, "explanation": "No trades to analyze."}
    
    # Calculate P&L for each trade first
    for trade in trades:
        if "pnl" not in trade:
            trade["pnl"] = _calculate_pnl(trade)
    
    # Overconfidence: high fraction_invested AND poor performance
    high_fraction_trades = []
    for trade in trades:
        fraction = trade.get("fraction_invested", 0)
        pnl_pct = (trade.get("pnl", 0) / trade.get("account_size", 1)) * 100
        
        # Overconfidence: high risk with low or negative returns
        if fraction > 0.25:  # More than 25% of account
            if pnl_pct < 5:  # Less than 5% return on account
                high_fraction_trades.append(trade)
    
    score = _safe_divide(len(high_fraction_trades), n)
    bias_detected = score > 0.2  # 20% of trades show overconfidence
    
    explanation = (
        f"High risk trades ({len(high_fraction_trades)}/{n}) with poor returns detected. "
        f"Average fraction invested: {sum(t.get('fraction_invested', 0) for t in trades)/n:.2%}"
    ) if bias_detected else "No strong overconfidence signals detected."
    
    return {
        "bias_detected": bias_detected,
        "confidence_score": min(score * 100, 100),
        "explanation": explanation
    }

def detect_fomo_bias(trades: List[Dict]) -> Dict[str, Any]:
    """
    Detect FOMO bias via notes analysis and trade patterns.
    """
    trades = _sort_trades_by_entry(trades)
    n = len(trades)
    if n == 0:
        return {"bias_detected": False, "confidence_score": 0.0, "explanation": "No trades to analyze."}
    
    fomo_keywords = [
        "fomo", "chasing", "panic", "miss out", "had to get in",
        "too good to miss", "going parabolic", "can't miss",
        "everyone's buying", "hype", "moon", "fear of missing"
    ]
    
    urgent_phrases = [
        "urgent", "quick", "immediately", "now or never",
        "last chance", "before it's too late"
    ]
    
    fomo_count = 0
    for trade in trades:
        notes = trade.get("notes", "").lower()
        reason = trade.get("trade_reason", "").lower()
        
        # Check notes for FOMO keywords
        if _text_contains_any(notes, fomo_keywords):
            fomo_count += 1
        # Check trade reason
        elif reason in ["fomo", "chasing", "trend_following"]:
            fomo_count += 1
        # Check for urgent language
        elif _text_contains_any(notes, urgent_phrases):
            fomo_count += 1
    
    score = _safe_divide(fomo_count, n)
    bias_detected = score > 0.2  # 20% of trades show FOMO
    
    triggers = []
    if score > 0:
        triggers.append(f"FOMO language in {fomo_count} trade(s)")
    
    explanation = (
        f"Detected FOMO indicators: {', '.join(triggers)}"
        if triggers else "No FOMO signals detected."
    )
    
    return {
        "bias_detected": bias_detected,
        "confidence_score": min(score * 100, 100),
        "explanation": explanation
    }

def detect_recency_bias(trades: List[Dict]) -> Dict[str, Any]:
    """
    Detect Recency bias by checking reaction to recent wins/losses.
    """
    trades = _sort_trades_by_entry(trades)
    n = len(trades)
    if n < 2:
        return {"bias_detected": False, "confidence_score": 0.0, "explanation": "Not enough trades."}
    
    # Calculate P&L for each trade
    for trade in trades:
        if "pnl" not in trade:
            trade["pnl"] = _calculate_pnl(trade)
        trade["pnl_pct"] = (trade["pnl"] / trade.get("account_size", 1)) * 100
    
    win_stay_count = 0
    loss_switch_count = 0
    recency_notes_count = 0
    
    recency_pattern = re.compile(r'\b(last|recent|again|this time)\b', re.I)
    
    for i in range(n - 1):
        current = trades[i]
        next_trade = trades[i + 1]
        
        # Win-stay: after win, same direction with increased size
        if current["pnl"] > 0:
            if (current.get("direction") == next_trade.get("direction") and
                next_trade.get("fraction_invested", 0) > current.get("fraction_invested", 0)):
                win_stay_count += 1
        
        # Loss-switch: after loss, switch direction
        elif current["pnl"] < 0:
            if current.get("direction") != next_trade.get("direction"):
                loss_switch_count += 1
        
        # Recency in notes
        if recency_pattern.search(current.get("notes", "")):
            recency_notes_count += 1
    
    total_patterns = win_stay_count + loss_switch_count
    score = _safe_divide(total_patterns, n - 1) * 0.7 + _safe_divide(recency_notes_count, n) * 0.3
    
    bias_detected = score > 0.3
    
    reasons = []
    if win_stay_count > 0:
        reasons.append(f"win-stay patterns ({win_stay_count})")
    if loss_switch_count > 0:
        reasons.append(f"loss-switch reactions ({loss_switch_count})")
    if recency_notes_count > 0:
        reasons.append(f"recency mentions in notes ({recency_notes_count})")
    
    explanation = "; ".join(reasons) if reasons else "No recency bias detected"
    
    return {
        "bias_detected": bias_detected,
        "confidence_score": min(score * 100, 100),
        "explanation": explanation
    }

def detect_confirmation_bias(trades: List[Dict]) -> Dict[str, Any]:
    """
    Detect Confirmation Bias by checking for selective information processing.
    """
    trades = _sort_trades_by_entry(trades)
    n = len(trades)
    if n == 0:
        return {"bias_detected": False, "confidence_score": 0.0, "explanation": "No trades to analyze."}
    
    confirmation_keywords = [
        "confirm", "proves", "as expected", "knew it", "obvious",
        "clearly", "evidence shows", "just as I thought"
    ]
    
    directional_streak = 0
    max_streak = 0
    current_streak = 0
    last_direction = None
    
    confirmation_count = 0
    
    for trade in trades:
        direction = trade.get("direction")
        notes = trade.get("notes", "").lower()
        
        # Check directional streaks
        if direction == last_direction:
            current_streak += 1
            max_streak = max(max_streak, current_streak)
        else:
            current_streak = 1
            last_direction = direction
        
        # Check confirmation language
        if _text_contains_any(notes, confirmation_keywords):
            confirmation_count += 1
    
    # Scores
    streak_score = _safe_divide(max_streak, n)
    confirmation_score = _safe_divide(confirmation_count, n)
    
    confidence_score = (streak_score * 0.6 + confirmation_score * 0.4) * 100
    bias_detected = confidence_score > 30  # 30% threshold
    
    explanation = (
        f"Directional streaks (max: {max_streak}) and confirmation language detected"
        if bias_detected else "No strong confirmation bias detected."
    )
    
    return {
        "bias_detected": bias_detected,
        "confidence_score": confidence_score,
        "explanation": explanation
    }

def detect_revenge_trading(trades: List[Dict]) -> Dict[str, Any]:
    """
    Detect Revenge Trading by checking for emotional reactions to losses.
    """
    trades = _sort_trades_by_entry(trades)
    n = len(trades)
    if n < 2:
        return {"bias_detected": False, "confidence_score": 0.0, "explanation": "Not enough trades."}
    
    # Calculate P&L
    for trade in trades:
        if "pnl" not in trade:
            trade["pnl"] = _calculate_pnl(trade)
    
    emotional_keywords = [
        "revenge", "angry", "frustrated", "rage", "upset", "mad",
        "get back", "make back", "recover losses"
    ]
    
    revenge_count = 0
    emotional_count = 0
    
    for i in range(1, n):
        prev_trade = trades[i - 1]
        current_trade = trades[i]
        
        # After a loss, increased position size
        if prev_trade["pnl"] < 0:
            prev_frac = prev_trade.get("fraction_invested", 0)
            curr_frac = current_trade.get("fraction_invested", 0)
            
            if curr_frac > prev_frac * 1.3:  # 30% increase after loss
                revenge_count += 1
        
        # Emotional language
        if _text_contains_any(current_trade.get("notes", ""), emotional_keywords):
            emotional_count += 1
    
    revenge_score = _safe_divide(revenge_count, n - 1)
    emotional_score = _safe_divide(emotional_count, n)
    
    confidence_score = (revenge_score * 0.7 + emotional_score * 0.3) * 100
    bias_detected = confidence_score > 25
    
    reasons = []
    if revenge_count > 0:
        reasons.append(f"increased risk after losses ({revenge_count})")
    if emotional_count > 0:
        reasons.append(f"emotional language ({emotional_count})")
    
    explanation = "; ".join(reasons) if reasons else "No revenge trading detected"
    
    return {
        "bias_detected": bias_detected,
        "confidence_score": confidence_score,
        "explanation": explanation
    }

def detect_herd_behavior(trades: List[Dict]) -> Dict[str, Any]:
    """
    Detect Herd Behavior by checking for popular assets and crowd-following language.
    """
    trades = _sort_trades_by_entry(trades)
    n = len(trades)
    if n == 0:
        return {"bias_detected": False, "confidence_score": 0.0, "explanation": "No trades to analyze."}
    
    popular_assets = {
        "crypto": ["btc", "bitcoin", "eth", "ethereum", "solana", "meme"],
        "tech": ["tsla", "nvda", "aapl", "meta", "amzn"],
        "trending": ["trending", "hot", "popular", "viral"]
    }
    
    herd_keywords = [
        "everyone", "crowd", "herd", "following", "popular",
        "social media", "twitter", "reddit", "what everyone is doing"
    ]
    
    herd_asset_count = 0
    herd_note_count = 0
    
    for trade in trades:
        asset_name = str(trade.get("asset_name", "")).lower()
        asset_type = str(trade.get("asset_type", "")).lower()
        notes = str(trade.get("notes", "")).lower()
        
        # Check for popular assets
        is_popular = False
        for category, assets in popular_assets.items():
            if any(asset in asset_name for asset in assets) or any(asset in asset_type for asset in assets):
                is_popular = True
                break
        
        if is_popular:
            herd_asset_count += 1
        
        # Check for herd language
        if _text_contains_any(notes, herd_keywords):
            herd_note_count += 1
    
    asset_score = _safe_divide(herd_asset_count, n)
    note_score = _safe_divide(herd_note_count, n)
    
    confidence_score = (asset_score * 0.6 + note_score * 0.4) * 100
    bias_detected = confidence_score > 30
    
    explanation = (
        f"Trading popular assets ({herd_asset_count}/{n}) and herd-following language"
        if bias_detected else "No strong herd behavior detected."
    )
    
    return {
        "bias_detected": bias_detected,
        "confidence_score": confidence_score,
        "explanation": explanation
    }

def detect_loss_aversion(trades: List[Dict]) -> Dict[str, Any]:
    """
    Detect Loss Aversion by checking holding patterns and exit behavior.
    """
    trades = _sort_trades_by_entry(trades)
    n = len(trades)
    if n < 2:
        return {"bias_detected": False, "confidence_score": 0.0, "explanation": "Not enough trades."}
    
    # Calculate P&L and holding period
    for trade in trades:
        if "pnl" not in trade:
            trade["pnl"] = _calculate_pnl(trade)
        
        # Calculate holding period in hours (simplified)
        entry = _parse_timestamp(trade.get("entry_timestamp", ""))
        exit_time = _parse_timestamp(trade.get("exit_timestamp", ""))
        if entry and exit_time:
            trade["holding_hours"] = (exit_time - entry).total_seconds() / 3600
        else:
            trade["holding_hours"] = 0
    
    # Analyze patterns
    quick_wins = 0
    slow_losses = 0
    total_wins = 0
    total_losses = 0
    
    for trade in trades:
        pnl = trade["pnl"]
        holding_hours = trade.get("holding_hours", 0)
        
        if pnl > 0:
            total_wins += 1
            if holding_hours < 24:  # Less than 1 day for winners
                quick_wins += 1
        elif pnl < 0:
            total_losses += 1
            if holding_hours > 72:  # More than 3 days for losers
                slow_losses += 1
    
    quick_win_score = _safe_divide(quick_wins, total_wins) if total_wins > 0 else 0
    slow_loss_score = _safe_divide(slow_losses, total_losses) if total_losses > 0 else 0
    
    confidence_score = ((quick_win_score + slow_loss_score) / 2) * 100
    bias_detected = confidence_score > 40
    
    reasons = []
    if quick_win_score > 0.4:
        reasons.append(f"quick profit taking ({quick_wins}/{total_wins} wins)")
    if slow_loss_score > 0.4:
        reasons.append(f"holding losses too long ({slow_losses}/{total_losses} losses)")
    
    explanation = "; ".join(reasons) if reasons else "No strong loss aversion detected."
    
    return {
        "bias_detected": bias_detected,
        "confidence_score": confidence_score,
        "explanation": explanation
    }

def detect_all_biases(trades: List[Dict]) -> Dict[str, Any]:
    """
    Run all bias detection functions.
    """
    # Pre-process trades: calculate P&L for all
    processed_trades = []
    for trade in trades:
        processed_trade = trade.copy()
        processed_trade["pnl"] = _calculate_pnl(trade)
        processed_trades.append(processed_trade)
    
    results = {}
    
    results["Overconfidence"] = detect_overconfidence(processed_trades)
    results["Loss Aversion"] = detect_loss_aversion(processed_trades)
    results["Confirmation Bias"] = detect_confirmation_bias(processed_trades)
    results["FOMO"] = detect_fomo_bias(processed_trades)
    results["Recency Bias"] = detect_recency_bias(processed_trades)
    results["Revenge Trading"] = detect_revenge_trading(processed_trades)
    results["Herd Behavior"] = detect_herd_behavior(processed_trades)
    
    # Calculate overall metrics
    detected_biases = [name for name, result in results.items() if result["bias_detected"]]
    total_score = sum(result["confidence_score"] for result in results.values())
    avg_score = total_score / len(results) if results else 0
    
    # Risk level based on number and severity of biases
    bias_count = len(detected_biases)
    avg_confidence = avg_score
    
    if bias_count >= 4 or avg_confidence > 60:
        risk_level = "High"
    elif bias_count >= 2 or avg_confidence > 40:
        risk_level = "Medium"
    else:
        risk_level = "Low"
    
    return {
        "detected_biases": detected_biases,
        "bias_count": bias_count,
        "overall_confidence": avg_score,
        "risk_level": risk_level,
        "details": results
    }
