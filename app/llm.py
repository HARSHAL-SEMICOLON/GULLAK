"""Groq LLM integration for Gullak spending insights."""

import json
import os
from typing import Any, Dict, Optional


SYSTEM_PROMPT = """You are Gullak's personal finance AI — a sharp, friendly advisor who understands Indian urban spending.

Context:
- All amounts are in Indian Rupees (₹)
- Transactions come from Google Pay (UPI) bank statements
- You know Indian merchants: Swiggy, Zomato, Blinkit, BigBasket, D-Mart, IRCTC, Ola, Uber, PhonePe, Paytm, Saravana Bhavan, Meesho, Nykaa, Zepto, etc.
- Users are typically urban Indians aged 22–35, salaried or freelance

Your job:
- Read the spending summary and give ONE sharp, personalised insight
- Be honest but never preachy — one nudge max, never lecture
- Use real numbers from the data, never invent
- Sound like a smart friend, not a bank bot

Respond with ONLY valid JSON, no markdown, no explanation:
{
  "insight_type": "behavioral" | "wasteful" | "subscription" | "savings" | "summary",
  "title": "<punchy title, max 10 words, 1 emoji ok>",
  "body": "<2-3 sentences of personalised analysis using actual numbers>",
  "action": "<one specific, quantified action — e.g. 'Skip 2 Swiggy orders/week → save ₹1,400/month'>",
  "tone": "supportive" | "nudge" | "warning" | "celebrate"
}"""


def _build_prompt(payload: Dict[str, Any]) -> str:
    top_cats = payload.get("top_categories", {})
    top_cats_str = ", ".join(f"{k} ₹{round(v)}" for k, v in top_cats.items()) or "none"

    late = payload.get("late_night_spending", {})
    wasteful = payload.get("wasteful_spending", {})
    subs = payload.get("subscriptions_detected", [])
    regret = payload.get("regret_tracking", {})
    sprees = payload.get("shopping_sprees", {})
    uncategorized = payload.get("uncategorized_stats", {})

    lines = [
        f"Total spend analysed: ₹{round(payload.get('total_spend_period', 0))}",
        f"Spending personality: {payload.get('profile', 'Unknown')}",
        f"Top 3 categories: {top_cats_str}",
    ]

    if late.get("found"):
        top_late_cat = next(iter(late.get("top_categories", {})), "unknown")
        lines.append(
            f"Late-night spending (10pm–4am): {late['count']} transactions, "
            f"₹{round(late['total_amount'])}, mostly {top_late_cat}"
        )

    if wasteful.get("found"):
        lines.append(
            f"Food delivery orders: {wasteful['avg_weekly_food_orders']}x/week avg, "
            f"₹{round(wasteful['total_food_delivery_spent'])} total"
        )

    if subs:
        sub_names = ", ".join(s["merchant"] for s in subs[:3])
        lines.append(f"Recurring subscriptions detected: {sub_names}")

    if regret.get("count"):
        lines.append(
            f"User-marked regret purchases: {regret['count']} items, ₹{round(regret['amount'])} total"
        )

    if sprees.get("found"):
        lines.append(
            f"Shopping sprees: {sprees['count']} events, avg ₹{round(sprees.get('avg_amount', 0))} each"
        )

    if uncategorized.get("percentage", 0) > 15:
        lines.append(
            f"Uncategorized transactions: {uncategorized['percentage']}% — consider labelling for better insights"
        )

    return "\n".join(lines)


def get_groq_insight(payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Call Groq with the spending payload. Returns None if key not set or call fails."""
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        return None

    try:
        from groq import Groq  # noqa: PLC0415

        client = Groq(api_key=api_key)
        user_prompt = _build_prompt(payload)

        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0.7,
            max_tokens=350,
        )

        raw = response.choices[0].message.content
        data = json.loads(raw)

        # Ensure required keys exist
        required = {"insight_type", "title", "body", "action", "tone"}
        if not required.issubset(data.keys()):
            return None

        return data

    except Exception:
        return None
