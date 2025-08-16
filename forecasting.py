from datetime import datetime, timedelta
from collections import defaultdict
from extensions import db
from models import StockMovement

def forecast_demand(product_id: int, days: int = 30):
    # Use OUT movements as demand
    q = (StockMovement.query
         .filter_by(product_id=product_id, type="OUT")
         .order_by(StockMovement.timestamp.asc())
         .all())
    if not q:
        return {"daily_rate": 0, "forecast": [0]*days, "suggested_reorder": 0}

    # Aggregate per day
    by_day = defaultdict(int)
    for m in q:
        d = m.timestamp.date()
        by_day[d] += abs(m.qty)

    # Moving average of last 30 days
    today = datetime.utcnow().date()
    window = [by_day.get(today - timedelta(days=i), 0) for i in range(1, 31)]
    avg = sum(window) / max(len(window), 1)

    # Simple seasonality: weight weekends a bit higher for retail (heuristic)
    forecast = []
    for i in range(1, days+1):
        day = today + timedelta(days=i)
        w = 1.15 if day.weekday() in (5, 6) else 1.0
        forecast.append(round(avg * w, 2))

    # Suggested reorder = next 14 days coverage + 10% buffer
    suggested = round(sum(forecast[:14]) * 1.10)
    return {"daily_rate": round(avg, 2), "forecast": forecast, "suggested_reorder": suggested}
