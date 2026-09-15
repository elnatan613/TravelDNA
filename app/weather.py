"""Trip weather, last-year comparison and practical packing guidance."""
from datetime import date, timedelta
import math

import requests


FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
HISTORY_URL = "https://archive-api.open-meteo.com/v1/archive"
FORECAST_SOURCE = "https://open-meteo.com/"
HISTORY_SOURCE = "https://open-meteo.com/en/docs/historical-weather-api"


def _same_date_last_year(day):
    """Keep the comparison useful for a 29 February departure too."""
    try:
        return day.replace(year=day.year - 1)
    except ValueError:
        return day.replace(year=day.year - 1, day=28)


def _daily_request(url, destination, start, end, fields):
    response = requests.get(url, params={
        "latitude": destination["lat"], "longitude": destination["lng"],
        "start_date": start.isoformat(), "end_date": end.isoformat(), "timezone": "auto",
        "daily": ",".join(fields),
    }, timeout=12)
    response.raise_for_status()
    return response.json()["daily"]


def _complete_rows(data, start, days, fields):
    expected = [(start + timedelta(days=i)).isoformat() for i in range(days)]
    if data.get("time") != expected:
        return []
    rows = []
    for index, day in enumerate(expected):
        try:
            values = {field: data[field][index] for field in fields}
        except (KeyError, IndexError, TypeError):
            return []
        if not all(isinstance(value, (int, float)) and math.isfinite(value) for value in values.values()):
            return []
        rows.append({"date": day, **values})
    return rows


def _historic_rows(destination, start, days):
    historic_start = _same_date_last_year(start)
    fields = ("temperature_2m_min", "temperature_2m_max", "precipitation_sum", "wind_speed_10m_max")
    data = _daily_request(HISTORY_URL, destination, historic_start, historic_start + timedelta(days=days - 1), fields)
    rows = _complete_rows(data, historic_start, days, fields)
    return [{
        "date": row["date"], "low": row["temperature_2m_min"], "high": row["temperature_2m_max"],
        "rain_mm": row["precipitation_sum"], "wind_kmh": row["wind_speed_10m_max"],
    } for row in rows]


def _comparison(forecast, historic):
    historic_rain = sum(row["rain_mm"] for row in historic)
    historic_wind = max(row["wind_kmh"] for row in historic)
    details = f"בשנה שעברה, באותם תאריכים, הטמפרטורות היו {min(row['low'] for row in historic):g}°–{max(row['high'] for row in historic):g}°"
    if historic_rain >= 1:
        details += f" וירדו בסך הכול כ־{historic_rain:g} מ״מ גשם"
    if historic_wind >= 35:
        details += f"; נמדדה גם רוח עד {historic_wind:g} קמ״ש"
    details += "."
    comparison = {"summary": details, "last_year_rain_mm": historic_rain, "last_year_max_wind_kmh": historic_wind}
    if forecast:
        current_low = sum(row["low"] for row in forecast) / len(forecast)
        prior_low = sum(row["low"] for row in historic) / len(historic)
        current_high = sum(row["high"] for row in forecast) / len(forecast)
        prior_high = sum(row["high"] for row in historic) / len(historic)
        comparison.update(low_difference=round(current_low - prior_low, 1), high_difference=round(current_high - prior_high, 1))
    return comparison


def _add_weather_items(items, rows, rain_key, fallback=False):
    if not rows:
        return
    low, high = min(row["low"] for row in rows), max(row["high"] for row in rows)
    if low < 10:
        items.extend(["מעיל חם", "שכבות חמות לערב"])
    elif low < 18:
        items.append("עליונית לערב")
    if high >= 24:
        items.extend(["בגדים קלים", "כובע וקרם הגנה"])
    if max(row[rain_key] for row in rows) >= (3 if fallback else 40):
        items.extend(["מעיל גשם או מטרייה", "נעליים עמידות למים"])


def _unique(items):
    return list(dict.fromkeys(items))


def packing_for_trip(destination, start, days, today=None):
    """Use a forecast when available, and observed conditions a year ago as context."""
    today = today or date.today()
    end = start + timedelta(days=days - 1)
    items = ["דרכון ומסמכי נסיעה", "מטען ומתאם חשמל", "נעליים נוחות", f"גרביים והלבשה תחתונה ל־{days} ימים", "כלי רחצה"]
    result = {
        "items": items, "daily": [], "historical_daily": [], "comparison": None,
        "source": FORECAST_SOURCE, "history_source": HISTORY_SOURCE, "status": "unavailable",
        "message": "אין תחזית מלאה לתאריכי הטיול. הרשימה בסיסית; כדאי לבדוק שוב סמוך ליציאה.",
    }

    forecast = []
    if start >= today and end <= today + timedelta(days=15):
        try:
            forecast_fields = ("temperature_2m_min", "temperature_2m_max", "precipitation_probability_max", "wind_speed_10m_max")
            data = _daily_request(FORECAST_URL, destination, start, end, forecast_fields)
            forecast = _complete_rows(data, start, days, forecast_fields)
            forecast = [{
                "date": row["date"], "low": row["temperature_2m_min"], "high": row["temperature_2m_max"],
                "rain": row["precipitation_probability_max"], "wind_kmh": row["wind_speed_10m_max"],
            } for row in forecast]
        except (requests.RequestException, ValueError, KeyError, IndexError, TypeError):
            forecast = []

    historic = []
    try:
        historic = _historic_rows(destination, start, days)
    except (requests.RequestException, ValueError, KeyError, IndexError, TypeError):
        historic = []

    if forecast:
        _add_weather_items(items, forecast, "rain")
        result.update(
            status="forecast", daily=forecast,
            message="רשימת האריזה מותאמת לתחזית בתאריכי הטיול. התחזית עשויה להשתנות.",
        )
    elif historic:
        _add_weather_items(items, historic, "rain_mm", fallback=True)
        result.update(
            status="historical",
            message="אין עדיין תחזית לתאריכי הטיול. הרשימה מותאמת למזג האוויר שנמדד באותם תאריכים בשנה שעברה — לא לתחזית.",
        )

    if historic:
        result.update(historical_daily=historic, comparison=_comparison(forecast, historic))
        if forecast and (max(row["rain_mm"] for row in historic) >= 10 or max(row["wind_kmh"] for row in historic) >= 45):
            items.append("שכבת גיבוי למזג אוויר משתנה")

    result["items"] = _unique(items)
    return result
