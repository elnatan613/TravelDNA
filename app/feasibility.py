"""Deterministic checks. Unknown evidence never counts as a passed check."""
from math import asin, cos, radians, sin, sqrt

from app.trip_models import Itinerary
from app.opening_hours import hours_for_date


def minutes(value):
    hours, mins = map(int, value.split(":"))
    return hours * 60 + mins


def distance_km(a, b):
    lat1, lat2 = radians(a.latitude), radians(b.latitude)
    delta = radians(b.longitude - a.longitude)
    return 6371 * 2 * asin(min(1, sqrt(sin((lat2-lat1)/2)**2 + cos(lat1)*cos(lat2)*sin(delta/2)**2)))


def validate_itinerary(trip: Itinerary, pace="balanced"):
    issues, unknown = [], []
    checked = 0
    limit = {"relaxed": 4, "balanced": 6, "busy": 8}[pace]
    for day in trip.days:
        prefix = day.date.isoformat()
        activities = sorted(day.activities, key=lambda a: a.start)
        checked += 1
        attraction_minutes = sum(
            max(0, minutes(a.end)-minutes(a.start))
            for a in activities if a.kind == "attraction"
        )
        if sum(a.kind == "attraction" for a in activities) > limit or sum(a.heavy for a in activities) > 3 or attraction_minutes > 600:
            issues.append(f"{prefix}: היום עמוס; כדאי להסיר פעילות או לפצל ליום נוסף.")
        for index, activity in enumerate(activities):
            label = f"{prefix} · {activity.name}"
            checked += 1
            start, end = minutes(activity.start), minutes(activity.end)
            if end <= start:
                issues.append(f"{label}: שעת הסיום אינה מאוחרת משעת ההתחלה.")
            # Restaurants and planned pauses are flexible choices, not named
            # venues in this itinerary. Opening-hours checks apply only to
            # attractions with dated evidence or a simple OSM schedule.
            if activity.kind == "attraction" and activity.opening_source and activity.opening_date == day.date and (
                activity.closed is True or (activity.opening_start and activity.opening_end)
            ):
                checked += 1
                if activity.closed or start < minutes(activity.opening_start) or end > minutes(activity.opening_end):
                    issues.append(f"{label}: הפעילות מחוץ לשעות הפתיחה שסופקו לתאריך זה.")
            elif activity.kind == "attraction":
                schedule = hours_for_date(activity.opening_hours, day.date)
                if schedule is None:
                    unknown.append(f"{label}: שעות הפתיחה לתאריך זה לא אומתו.")
                else:
                    checked += 1
                    status, opening_start, opening_end = schedule
                    if status == "closed":
                        issues.append(f"{label}: לפי שעות OpenStreetMap המקום סגור בתאריך זה.")
                    elif start < minutes(opening_start) or end > minutes(opening_end):
                        issues.append(f"{label}: הפעילות מחוץ לשעות OpenStreetMap שפורסמו למקום.")
            if index == 0:
                continue
            previous = activities[index-1]
            gap = start - minutes(previous.end)
            checked += 1
            if gap < 0:
                issues.append(f"{label}: הפעילות חופפת לפעילות הקודמת.")
            if activity.kind != "attraction":
                continue
            previous = next((a for a in reversed(activities[:index]) if a.kind == "attraction"), None)
            if previous is None:
                continue
            gap = start - minutes(previous.end)
            if activity.travel_minutes is not None and activity.travel_source:
                checked += 1
                if gap < activity.travel_minutes:
                    issues.append(f"{label}: נדרשות {activity.travel_minutes} דקות מעבר, אך הוקצו {max(0, gap)}.")
            else:
                unknown.append(f"{label}: זמן המעבר מהפעילות הקודמת לא אומת.")
                if all(a.latitude is not None and a.longitude is not None and a.location_source for a in (previous, activity)):
                    km = distance_km(previous, activity)
                    # A conservative impossibility screen, never a routing estimate.
                    if km > 2 and gap < km / 130 * 60:
                        issues.append(f"{label}: מרחק אווירי של {km:.1f} ק״מ אינו סביר בזמן המעבר שהוקצה.")
    coverage_percent = round(100 * checked / (checked + len(unknown)))
    issue_penalty = min(60, len(issues) * 12)
    evidence_penalty = round((100 - coverage_percent) * 0.4)
    return {
        "status": "issues" if issues else "partial" if unknown else "passed",
        "issues": issues, "unknown": unknown, "checks_performed": checked,
        "coverage_percent": coverage_percent,
        # A reproducible feasibility score: verified coverage supplies up to
        # 40 points of the uncertainty component; concrete conflicts cost 12.
        "score": max(0, 100 - issue_penalty - evidence_penalty),
        "score_explanation": {
            "issue_penalty": issue_penalty,
            "evidence_penalty": evidence_penalty,
        },
    }
