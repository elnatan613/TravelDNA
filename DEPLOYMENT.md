# פריסה ל־Railway

הפרויקט מוכן לפריסה כשירות אחד: FastAPI מגיש את ה־API ואת קבצי ה־React שנבנים בתוך ה־Docker image. קובץ ה־Docker משתמש ב־`requirements.production.txt`, שמכיל רק את החבילות הנדרשות לשרת ואינו מתקין את Streamlit וכלי הבדיקות של סביבת הפיתוח.

1. היכנסו ל־[Railway](https://railway.app) עם חשבון GitHub.
2. בחרו **New Project** ואז **Deploy from GitHub repo**, ובחרו את `elnatan613/TravelDNA` ואת הענף `main`.
3. ב־**Variables** הוסיפו `GEMINI_API_KEY` עם מפתח ייעודי ל־TravelDNA, והשתמשו בתפריט שלידו כדי לבחור **Seal**. אין להעלות את קובץ `.env` ל־GitHub. השרת מגביל בקשות AI לפי מבקר, כדי למנוע שימוש בלתי מבוקר במכסה.
4. המתינו לסיום הבנייה. Railway מזהה את `Dockerfile` ובונה את ממשק ה־React ואת שרת ה־Python יחד.
5. תחת **Settings → Networking** לחצו **Generate Domain**. זהו הקישור הציבורי של האפליקציה.

Railway בודק את `GET /health`, כך שאפשר לוודא שהשירות עלה על ידי פתיחת `https://<your-domain>/health`.

## הערה על עלות

האפליקציה טוענת מודל embedding של Python בעת שימוש בבניית מסלול, ולכן מומלץ להתחיל במסלול Hobby של Railway ולבחור לפחות 1GB RAM. אפשר להגדיל את הזיכרון אם בניית מסלול נכשלת או נקטעת.
