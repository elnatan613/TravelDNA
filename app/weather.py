"""Date-specific Open-Meteo forecast and transparent packing fallback."""
from datetime import date, timedelta
import math
import requests


def packing_for_trip(destination, start, days, today=None):
    today = today or date.today()
    end = start + timedelta(days=days-1)
    items = ["דרכון ומסמכי נסיעה", "מטען ומתאם חשמל", "נעליים נוחות", f"גרביים והלבשה תחתונה ל־{days} ימים", "כלי רחצה"]
    result = {"items": items, "daily": [], "source": "https://open-meteo.com/", "status": "unavailable",
              "message": "אין תחזית מלאה לתאריכי הטיול. הרשימה בסיסית; כדאי לבדוק שוב סמוך ליציאה."}
    if start < today or end > today + timedelta(days=15):
        return result
    try:
        response = requests.get("https://api.open-meteo.com/v1/forecast", params={
            "latitude": destination["lat"], "longitude": destination["lng"],
            "start_date": start.isoformat(), "end_date": end.isoformat(), "timezone": "auto",
            "daily": "temperature_2m_min,temperature_2m_max,precipitation_probability_max",
        }, timeout=12)
        response.raise_for_status()
        data = response.json()["daily"]
        expected = [(start + timedelta(days=i)).isoformat() for i in range(days)]
        if data["time"] != expected:
            return result
        rows = []
        for i, day in enumerate(expected):
            values = [data[key][i] for key in ("temperature_2m_min", "temperature_2m_max", "precipitation_probability_max")]
            if not all(isinstance(v, (int, float)) and math.isfinite(v) for v in values):
                return result
            rows.append(dict(date=day, low=values[0], high=values[1], rain=values[2]))
        low, high = min(r["low"] for r in rows), max(r["high"] for r in rows)
        if low < 10:
            items.extend(["מעיל חם", "שכבות חמות לערב"])
        elif low < 18:
            items.append("עליונית לערב")
        if high >= 24:
            items.extend(["בגדים קלים", "כובע וקרם הגנה"])
        if max(r["rain"] for r in rows) >= 40:
            items.extend(["מעיל גשם או מטרייה", "נעליים עמידות למים"])
        result.update(status="forecast", daily=rows, message="רשימת האריזה מותאמת לתחזית בתאריכי הטיול. התחזית עשויה להשתנות.")
    except (requests.RequestException, ValueError, KeyError, IndexError, TypeError):
        pass
    return result
