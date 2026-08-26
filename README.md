# TravelDNA

מערכת שמודדת פרופיל העדפות נסיעה קונקרטי ומתאימה לו יעד טיול (עיר באירופה),
ובהמשך בונה מסלול טיול אישי - פרויקט גמר בקורס AI Engineering.

## הרעיון בקצרה

1. שאלון קצר (שאלות סגורות 1-5 + שאלה פתוחה אחת) → **Travel Profile**
2. השוואת הפרופיל לרשימת ערים מתויגות → **3 יעדים מומלצים**
3. בחירת יעד + ימים + תקציב → **RAG + Agent** → מסלול טיול אישי

## Travel Profile - 7 צירים מדודים

בכוונה **לא** ממדי "אישיות" מעורפלים (כמו "הרפתקנות") - כל ציר הוא ממד בודד,
מדיד וברור, בסקאלה 0 עד 1:

| ציר | מה נמדד |
|---|---|
| `urban` | העדפה לסביבה עירונית (0=טבע/כפר, 1=עיר) |
| `culture` | עניין באתרים תרבותיים (0=נמוך, 1=גבוה) |
| `nightlife` | עניין בפעילות ערב/בילוי (0=נמוך, 1=גבוה) |
| `social` | העדפה לפעילויות עם אנשים (0=שקט/עצמאות, 1=חברתי) |
| `activity_density` | כמה פעילויות ביום (0=מעט, 1=הרבה) |
| `food` | חשיבות אוכל בטיול (0=נמוכה, 1=גבוהה) |
| `price_sensitivity` | רגישות למחיר (0=פחות רגיש/יוקרתי, 1=מאוד רגיש/תקציבי) |

**כשרות היא constraint, לא ציר** - בצד המשתמש זה בוליארי (`kosher: true/false`),
ובצד העיר זה שדה נפרד `kosher_availability` (0-1, "כמה קל להסתדר בעיר הזו"),
לא חלק מ"אופי" העיר.

הגדרות מדויקות ורשימת הערים הרשמית נמצאות ב-`config.py` - זה "החוזה" המשותף.

## מקורות דאטה (לצד היעדים)

לא "דאטהבייס" משלנו - אלה **מקורות דאטה חיצוניים** (שירותים/API-ים של גורם
שלישי) שאנחנו שולפים מהם, ומרכיבים מהתשובות שלהם את `destinations.json`:

| שדה | מקור | הערות |
|---|---|---|
| קואורדינטות, אוכלוסייה, מדינה | [GeoNames](https://www.geonames.org) | דורש חשבון חינמי + הפעלה נפרדת של ה-Free Web Services בהגדרות החשבון |
| `urban` | GeoNames (אוכלוסייה, מנורמל min-max) | לא Overpass - ניסינו יחס landuse ב-OSM אבל זה נתן תוצאות לא הגיוניות (למשל ציון "טבעי" לפריז), כי תיוג landuse לא עקבי בין ערים; population הוא מדד פשוט ואמין יותר |
| `culture`, `nightlife`, `food`, `social`, `activity_density` | [Overpass API](https://overpass-api.de) (OpenStreetMap) | חינמי לגמרי, בלי הרשמה ובלי מפתח. במקור תכננו OpenTripMap, אבל תהליך ההרשמה שלהם קרס בעקביות (שגיאת שרת 500) |
| `price_sensitivity` | [Numbeo](https://www.numbeo.com) - Cost of Living Index | **נאסף ידנית** (לא סקריפט אוטומטי) מהדף הציבורי - ה-Terms of Use של Numbeo אוסרים scraping אוטומטי בלי אישור כתוב, אבל מתירים שימוש אקדמי עם קרדיט. ה-API הרשמי שלהם בתשלום בלבד ($260+/חודש) |
| `kosher_availability` | Overpass (OSM) - `religion=jewish` + `diet:kosher=yes` | אותו מקור כמו הצירים למעלה. שקלנו Chabad.org (אין API ציבורי) ו-Google Places API (דורש חשבון עם כרטיס אשראי) ופסלנו את שניהם |
| בסיס ידע RAG (`rag/knowledge_base/`) | [Wikivoyage](https://en.wikivoyage.org) - מדריכי טיולים | רישיון CC BY-SA, **API רשמי וחינמי** (מיועד לגישה תכנותית, לא כמו Numbeo) - נשלף לכל 18 הערים שב-`config.CITIES`. Embeddings מחושבים מקומית (`sentence-transformers`, מודל `all-mpnet-base-v2`) - בלי API/מפתח חיצוני |
| Trip Planning Agent (`agent/trip_planner.py`) | [Gemini API](https://ai.google.dev) (`gemini-3.5-flash`) | ה-LLM היחיד בפרויקט - יש לו שכבת חינם אמיתית בלי כרטיס אשראי (בדקנו במפורש; ב-Anthropic/OpenAI זה לא המצב). דורש `GEMINI_API_KEY` משלכם (חינמי, אישי - https://aistudio.google.com/apikey) |

הכל (חוץ מ-Numbeo, שהוא טבלה ידנית קבועה בקוד) נשלף מחדש בכל הרצה של
`python scripts/destination_scraper.py`, ומיוצא ל-`data/processed/destinations.json`
(קובץ JSON שטוח - גם הוא לא דאטהבייס, רק תוצר). בסיס הידע של RAG נשלף
בנפרד ע"י `python rag/build_knowledge_base.py`.

## איך לעבוד עם זה בשניים במקביל

הפרויקט מחולק לשני חלקים עצמאיים שנפגשים רק דרך `config.py` ודרך פורמט
קובץ ה-JSON של היעדים.

**אלנתן - "צד היעדים"**
`scripts/` + `matching/` + `data/`
שליפת דאטה על ערים, תיוג לפי 7 הצירים + `kosher_availability`, ומנוע ההתאמה.

**דין - "צד המשתמש"**
`nlp/`
המרת תשובות השאלון הסגור לפרופיל בסיסי (rule-based, בלי AI), ושילוב עם
חילוץ LLM מהשאלה הפתוחה בלבד.

מי שעובד בצד אחד לא נוגע בקבצים של הצד השני. הקובץ היחיד שדורש תיאום הוא
`config.py` - כל שינוי בשמות הצירים משפיע על שניכם.

## מבנה התיקיות

```
travel-dna/
├── config.py              # 7 הצירים, המשקלים, רשימת הערים - "החוזה" המשותף
├── data/
│   ├── raw/                # דאטה גולמי לפני עיבוד
│   └── processed/          # destinations.json - הפלט הסופי לשימוש matching
├── scripts/
│   ├── destination_scraper.py   # GeoNames + Overpass/OSM (urban/culture/nightlife וכו')
│   ├── numbeo_fetcher.py        # ציר price_sensitivity (Numbeo Cost of Living Index)
│   └── kashrut_fetcher.py       # kosher_availability לכל עיר (Overpass/OSM - בתי כנסת + diet:kosher)
├── nlp/
│   └── profile_extractor.py     # rule-based mapping + LLM לטקסט חופשי בלבד
├── matching/
│   └── matcher.py                # מרחק משוקלל + דירוג יעדים (עובד עם דאטה דמה)
├── app/
│   ├── demo.py                    # דמו Streamlit שמחבר הכל (תלוי ב-nlp/)
│   └── try_matching.py            # כלי ניסוי ידני ל-matcher.py - וקטור + kosher constraint, בלי nlp/
├── rag/
│   ├── build_knowledge_base.py    # בונה בסיס ידע מ-Wikivoyage לכל config.CITIES
│   ├── retriever.py                # חיפוש סמנטי (cosine similarity) בבסיס הידע שנבנה
│   └── knowledge_base/             # תוצר: {city}_chunks.json + {city}_embeddings.npy
├── agent/
│   └── trip_planner.py            # TripPlanningAgent - Gemini + 2 כלים (rag/retriever.py + budget)
└── tests/
```

## התקנה

```bash
pip install -r requirements.txt
```

יש להירשם (חינם) ולקבל מפתחות - שני מקורות דורשים מפתח (שאר המקורות
בטבלה למעלה לא, ראו שם):
- **GeoNames**: https://www.geonames.org/login - ואז חשוב **גם** להפעיל
  את ה-Free Web Services בעמוד https://www.geonames.org/manageaccount
  (לא מספיק רק להירשם)
- **Gemini** (ל-`agent/trip_planner.py`): https://aistudio.google.com/apikey
  - חינמי, בלי כרטיס אשראי, עם חשבון Google אישי (לא קשור לחשבון ארגוני
    של מקום עבודה - זה API אחר ונפרד, גם אם דומה בשם)

הכי פשוט: קובץ `.env` בשורש הפרויקט (כבר ב-`.gitignore`, לא נכנס לגיט):
```
GEONAMES_USERNAME=your_username
GEMINI_API_KEY=your_key
```
(אפשר גם `setx VAR_NAME "value"` ב-PowerShell/CMD - אבל שימו לב: משתני
סביבה שהוגדרו כך נראים רק לתהליכים/טרמינלים *חדשים* שנפתחו אחרי ה-setx,
לא לתהליכים שכבר היו פתוחים)

## הרצה מהירה (עם דאטה דמה, בלי לחכות לשום API)

```bash
python matching/matcher.py       # בודק את מנוע ההתאמה על נתוני דוגמה
python nlp/profile_extractor.py  # בודק את בניית הפרופיל (rule-based + דמה ל-LLM)
streamlit run app/demo.py        # דמו מלא, עם התראה אם דאטה חסר

# ניסוי ידני במנוע ההתאמה על הדאטה האמיתי (destinations.json) - בלי nlp/ בכלל:
streamlit run app/try_matching.py

# חיפוש סמנטי בבסיס הידע של RAG (כל 18 הערים כבר בנויות ובגיט):
python rag/retriever.py "modernist architecture by Gaudi" Barcelona

# הסוכן המלא - בונה מסלול יום-יום (דורש GEMINI_API_KEY ב-.env):
python agent/trip_planner.py Paris 3 500 "loves art and food, not much into nightlife"
```

## סטטוס נוכחי

- [x] מבנה פרויקט + config משותף עם 7 הצירים המדודים
- [x] מנוע התאמה (מרחק משוקלל) - עובד
- [x] שלד NLP: rule-based mapping לשאלות סגורות + validation/clamping - עובד
- [x] שליפת דאטה גיאוגרפי (GeoNames + Overpass/OSM) - עובד, הורחב ל-18 ערים, destinations.json מוכן
- [x] ציר `price_sensitivity` (Numbeo Cost of Living Index, נאסף ידנית - לא scraping, ראו scripts/numbeo_fetcher.py)
- [x] `kosher_availability` לכל עיר (Overpass/OSM - בתי כנסת + diet:kosher, ראו scripts/kashrut_fetcher.py)
- [x] `matcher.py` מכבד את אילוץ הכשרות בפועל (`requires_kosher` - סינון קשה, לא ציר משוקלל)
- [x] RAG - בסיס ידע מ-Wikivoyage לכל 18 הערים שב-`config.CITIES`, חיפוש סמנטי מקומי (ראו rag/)
- [x] Trip Planning Agent (`agent/trip_planner.py`) - Gemini + function calling, 2 כלים (חיפוש RAG + הערכת תקציב), עובד ונבדק על Paris/3 ימים/500$
- [ ] חילוץ LLM אמיתי מהטקסט הפתוח - כרגע דמה מחזירה dict ריק
- [ ] דמו מחובר סופית
