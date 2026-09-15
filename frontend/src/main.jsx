import React, { useEffect, useState } from 'react';
import { createRoot } from 'react-dom/client';
import './style.css';
import { download } from './export.js';
import Questionnaire from './Questionnaire.jsx';
import {DRAFT_KEY, freshDraft, restoreDraft, surveyPayload, inferredPace, PARTIES} from './survey-state.js';

function localDate() { const d = new Date(); return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`; }
async function api(path, data) {
  let response;
  try { response = await fetch(`/api/${path}`, data ? { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(data) } : {}); }
  catch { throw new Error('החיבור לשרת נותק. בדקו שהשרת פועל ונסו שוב.'); }
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(typeof body.detail === 'string' ? body.detail : 'לא ניתן להשלים את הבקשה. בדקו את הנתונים ונסו שוב.');
  }
  return response.json();
}
function App() {
  const [cities, setCities] = useState([]), [city, setCity] = useState('Paris');
  const [draft,setDraft] = useState(()=>{try{return restoreDraft(sessionStorage.getItem(DRAFT_KEY));}catch{return freshDraft();}});
  const [surveyComplete,setSurveyComplete] = useState(false), [matches,setMatches] = useState(null);
  const [hasSignal,setHasSignal] = useState(true);
  const [start, setStart] = useState(localDate()), [days, setDays] = useState(3), [budget, setBudget] = useState(500), [pace, setPace] = useState('balanced');
  const [busy, setBusy] = useState(''), [error, setError] = useState(''), [result, setResult] = useState(null), [tab, setTab] = useState('trip'), [hours, setHours] = useState(true);
  const [packed, setPacked] = useState({});
  const [planStage, setPlanStage] = useState(0);
  const planStages = ['בונים מסלול לפי הבחירות שלכם', 'מאתרים כתובות ופרטים על המקומות', 'בודקים שעות פתיחה וזמני הליכה'];
  const validationGaps = result ? result.validation.unknown.reduce((gaps, item) => {
    if (item.includes('שעות הפתיחה')) gaps.opening += 1;
    else if (item.includes('זמן המעבר')) gaps.travel += 1;
    else gaps.other += 1;
    return gaps;
  }, {opening: 0, travel: 0, other: 0}) : {opening: 0, travel: 0, other: 0};
  useEffect(() => { api('cities').then(setCities).catch(e => setError(e.message)); }, []);
  useEffect(()=>{try{sessionStorage.setItem(DRAFT_KEY,JSON.stringify(draft));}catch{/* Session storage is optional. */}},[draft]);
  useEffect(() => {
    if (busy !== 'plan') return undefined;
    setPlanStage(0);
    const addresses = window.setTimeout(() => setPlanStage(1), 2500);
    const validation = window.setTimeout(() => setPlanStage(2), 6500);
    return () => { window.clearTimeout(addresses); window.clearTimeout(validation); };
  }, [busy]);
  const selected = cities.find(c => c.city === city);
  async function finishSurvey(direct) {
    setBusy('match'); setError('');
    try {
      const survey=surveyPayload(draft);
      if(direct){setMatches(null);setPace(inferredPace(survey.choices));}
      else {const data=await api('discover',survey);setMatches(data.results);setHasSignal(data.has_signal);setPace(data.pace);if(data.results.length)setCity(data.results[0].city);}
      setResult(null);setSurveyComplete(true);window.scrollTo({top:0,behavior:'instant'});
    }
    catch (e) { setError(e.message); } finally { setBusy(''); }
  }
  async function plan(e) {
    e.preventDefault(); setBusy('plan'); setError(''); setResult(null);
    try {
      setResult(await api('plan', {city, start_date: start, days: Number(days), budget: Number(budget), pace, survey:surveyPayload(draft)})); setPacked({}); setTab('trip');
    } catch(e) { setError(e.message); } finally { setBusy(''); }
  }
  function exportPdf() { window.print(); }
  function newTrip() {
    setDraft(freshDraft());setSurveyComplete(false);setMatches(null);setResult(null);setError('');
    setCity('Paris');setStart(localDate());setDays(3);setBudget(500);setPace('balanced');setPacked({});
  }
  return <><header><a className="brand" href="/" dir="ltr"><span className="brand-icon">✳</span> TravelDNA</a><span>פחות תכנון. יותר חוויות.</span><span className="header-tag">המסע מתחיל בכם ↗</span></header>
    <main>{!surveyComplete ? <Questionnaire draft={draft} onChange={setDraft} onFinish={finishSurvey} busy={!!busy} error={error}/> : <>
    <div className="trip-edit"><div><p className="eyebrow">הטיול שלכם, הבחירות שלכם</p><h1>עכשיו, לאן נוסעים?</h1></div><div className="trip-edit-actions"><button className="secondary" disabled={!!busy} onClick={()=>{setError('');setSurveyComplete(false);setDraft(prev=>({...prev,stage:'party',index:0}));}}>↶ עריכת החוויות</button><button className="text-button" disabled={!!busy} onClick={newTrip}>טיול חדש</button></div></div>
    <div className="workspace"><aside className="card controls"><div className="section-title"><span className="step">✳</span><h2>מחברים את כל הפרטים</h2></div><p className="muted">{PARTIES[draft.party]} · הבחירות שלכם ילוו את המסלול</p>
      {matches!==null && <><p className="discovery-note">{hasSignal?'שלושה כיוונים לפי החוויות שבחרתם:':'אין עדיין מספיק מידע להעדפה ממוקדת. הנה כמה אפשרויות להתחיל מהן:'}</p><div className="matches">{matches.length===0?<p className="selection-note">לא נמצאו יעדים שעומדים בדרישות. אפשר לערוך את ההערות או לבחור יעד לבדיקה ידנית.</p>:matches.map(m=><button key={m.city} className={city===m.city?'selected':''} onClick={()=>setCity(m.city)}>{m.label}<span>{m.match_percent===null?'אפשרות לטיול':`${m.match_percent}% התאמה`}</span></button>)}</div></>}
      <form onSubmit={plan}><label>היעד שלכם<select value={city} onChange={e => setCity(e.target.value)} disabled={!cities.length}>{cities.map(c => <option key={c.city} value={c.city}>{c.label}</option>)}</select></label>
      <div className="field-row"><label>תאריך יציאה<input required type="date" min={localDate()} value={start} onChange={e => setStart(e.target.value)}/></label><label>מספר ימים<input required type="number" min="1" max="14" value={days} onChange={e => setDays(e.target.value)}/></label></div>
      <label>תקציב כולל בדולר<input required type="number" min="1" max="1000000" value={budget} onChange={e => setBudget(e.target.value)}/><small>ללא טיסות ולינה</small></label>
      <label>הקצב שלכם<select value={pace} onChange={e => setPace(e.target.value)}><option value="relaxed">רגוע · זמן לנשום</option><option value="balanced">מאוזן · קצת מכל דבר</option><option value="busy">מלא · להספיק ולגלות</option></select></label>
      <button className="primary wide" disabled={!!busy || !cities.length}>{busy === 'plan' ? 'בונה את הטיול שלכם…' : 'בנו לי מסלול אישי ←'}</button></form></aside>
      <section className="results" aria-live="polite">{error && <div className="error" role="alert">{error}</div>}{busy === 'plan' ? <div className="card empty"><div className="spinner"/><h2>הטיול שלכם מקבל צורה</h2><p>{planStages[planStage]}</p><ol className="build-steps">{planStages.map((stage, index) => <li key={stage} className={index <= planStage ? 'active' : ''}><span className="build-index">{index < planStage ? '✓' : String(index + 1).padStart(2, '0')}</span><span className="build-label">{stage}</span></li>)}</ol><small>אפשר להשאיר את העמוד פתוח בזמן שהתכנון נמשך.</small></div> : !result ? <div className="card empty"><div className="compass">✳</div><p className="eyebrow">מקום חדש. סיפור חדש.</p><h2>{selected ? `אולי ${selected.label}?` : 'המסלול הבא מתחיל כאן'}</h2><p>{selected?.background || 'בחרו יעד ותאריכים, ואנחנו נחבר את כל הפרטים.'}</p><div className="empty-grid"><span>01<br/><b>בחרו מה מתאים</b></span><span>02<br/><b>קבלו מסלול</b></span><span>03<br/><b>צאו לגלות</b></span></div><small>רקע היעדים: Wikivoyage · CC BY-SA 4.0</small></div> : <>
      <div className="result-heading"><div><p className="eyebrow">ההרפתקה שלכם מוכנה</p><h2>{cities.find(c=>c.city===result.request.city)?.label} · {result.request.days} ימים</h2><p className="muted">{result.request.start_date} · {result.request.budget} דולר</p></div><button className="secondary no-print" onClick={exportPdf}>↓ ייצוא ל־PDF</button></div>
      <nav className="tabs" aria-label="פרטי הטיול">{[['trip','המסלול שלי'],['validation','בדיקת היתכנות'],['packing','מה במזוודה?']].map(([id,label]) => <button key={id} aria-pressed={tab===id} className={tab===id?'active':''} onClick={()=>setTab(id)}>{label}</button>)}</nav>
      {tab === 'trip' && <><div className="card summary"><p>{result.itinerary.summary}</p><label className="check"><input type="checkbox" checked={hours} onChange={e=>setHours(e.target.checked)}/> הצגת פירוט שעות משוער</label></div>{result.itinerary.days.map((d,i)=><article className="card day" key={d.date}><div className="day-title"><span className="step">{String(i+1).padStart(2,'0')}</span><h3>יום {i+1}</h3><span className="muted">{d.date}</span></div>{d.activities.map((a,j)=><div className="activity" key={j}>{hours && <time dir="ltr">{a.start}–{a.end}</time>}<div><h4>{a.name}</h4><p>{a.description}</p>{a.travel_minutes !== null && a.travel_minutes !== undefined && <p className="travel-time">כ־{a.travel_minutes} דקות הליכה מהאטרקציה הקודמת · OpenStreetMap</p>}{a.address && <div className="place-details">{a.venue_type && <span>{a.venue_type}</span>}<span><b>כתובת:</b> {a.address}{a.map_url && <> · <a href={a.map_url} target="_blank" rel="noreferrer">למפה ↗</a></>}</span>{a.opening_hours && <span><b>שעות לפי OpenStreetMap:</b> <b dir="ltr">{a.opening_hours}</b></span>}{a.estimated_cost && <span><b>עלות משוערת:</b> {a.estimated_cost}</span>}{a.website && <a href={a.website} target="_blank" rel="noreferrer">האתר הרשמי ↗</a>}<small>כתובת ושעות: OpenStreetMap · עלות היא הערכה, לא מחיר רשמי</small></div>}</div></div>)}</article>)}<div className="sources">מקורות: {result.itinerary.sources.filter(s=>/^https?:\/\//i.test(s)).map((s,i)=><a key={i} href={s} target="_blank" rel="noreferrer">מקור {i+1} ↗</a>)}</div></>}
      {tab === 'validation' && <div className="card report"><p className="eyebrow">בדיקת המסלול</p><h3>{result.validation.status==='issues'?'יש נקודות שדורשות שינוי':result.validation.status==='passed'?'המסלול עבר את הבדיקות':'המסלול תקין, עם פרטים שעדיין צריך לאמת'}</h3><div className="score">{result.validation.score}<small>/100</small></div><p className="muted">ציון היתכנות מחושב: בעיות אמיתיות מורידות 12 נקודות כל אחת, וחוסר בנתונים מוריד עד 40 נקודות לפי כיסוי הבדיקות.</p><p>{result.validation.checks_performed} בדיקות בוצעו · כיסוי בדיקות {result.validation.coverage_percent}%</p><p className="muted">הבדיקה מחפשת עומס, חפיפות ושעות פתיחה שסותרות את המסלול. רק בעיה ממשית מופיעה כהתראה.</p>{result.validation.issues.map((s,i)=><p className="notice" key={i}>{s}</p>)}{!result.validation.issues.length && <p className="validation-ok">לא נמצאה התנגשות בזמנים או עומס חריג במסלול.</p>}{result.validation.unknown.length > 0 && <section className="validation-gaps"><h4>מה כדאי להשלים לפני היציאה</h4>{validationGaps.opening > 0 && <p><b>{validationGaps.opening} אטרקציות</b> ללא שעות פתיחה מאומתות. שעות שמצאנו מופיעות בכרטיס של כל מקום; את השאר כדאי לבדוק באתר הרשמי לפני הזמנה.</p>}{validationGaps.travel > 0 && <p><b>{validationGaps.travel} מעברים</b> ללא זמן נסיעה מאומת. שמרו מרווח בין התחנות או בדקו את המסלול במפה ביום הטיול.</p>}{validationGaps.other > 0 && <p>יש עוד {validationGaps.other} פריטי מידע שלא אומתו.</p>}<details><summary>פירוט הפריטים לבדיקה ({result.validation.unknown.length})</summary><ul>{result.validation.unknown.map((s,i)=><li key={i}>{s}</li>)}</ul></details></section>}<hr/><h3>המלצות המדריך</h3>{result.guide_review?<><p className="muted">ההמלצות נוצרו על ידי מודל ומשמשות כהצעות בלבד.</p><ul>{result.guide_review.notes.map((s,i)=><li key={i}>{s}</li>)}</ul></>:<p>המלצות המדריך אינן זמינות כרגע. הבדיקות האוטומטיות מופיעות למעלה.</p>}</div>}
      {tab==='packing' && <div className="card report"><p className="eyebrow">לארוז בראש שקט</p><h3>המזוודה שלכם</h3><p>{result.packing.message}</p>{result.packing.daily.length > 0 && <><h4 className="weather-heading">התחזית לתאריכי הטיול</h4><div className="weather">{result.packing.daily.map(d=><div key={d.date}><b>{d.date}</b><span dir="ltr">{d.low}°–{d.high}°</span><small>{d.rain}% סיכוי לגשם{d.wind_kmh !== undefined && <> · רוח עד {d.wind_kmh} קמ״ש</>}</small></div>)}</div></>}{result.packing.comparison && <section className="weather-comparison"><h4>מה קרה באותם תאריכים בשנה שעברה</h4><p>{result.packing.comparison.summary}</p><div className="weather historical">{(result.packing.historical_daily || []).map(d=><div key={d.date}><b>{d.date}</b><span dir="ltr">{d.low}°–{d.high}°</span><small>{d.rain_mm} מ״מ גשם · רוח עד {d.wind_kmh} קמ״ש</small></div>)}</div><small>זהו מזג אוויר שנמדד בפועל בשנה שעברה, והוא הקשר שימושי לאריזה — לא תחזית לשנה הזו.</small></section>}<div className="packing-list">{result.packing.items.map((s,i)=><label key={s} className={packed[i]?'packed':''}><input type="checkbox" checked={!!packed[i]} onChange={e=>setPacked({...packed,[i]:e.target.checked})}/>{s}</label>)}</div>{result.packing.status==='forecast'&&<a href={result.packing.source} target="_blank" rel="noreferrer">נתוני תחזית: Open-Meteo ↗</a>}{result.packing.historical_daily?.length > 0 && <><br/><a href={result.packing.history_source} target="_blank" rel="noreferrer">נתוני מזג אוויר משנה שעברה: Open-Meteo ↗</a></>}</div>}
      <button className="text-button no-print" onClick={()=>download(`TravelDNA-${result.request.start_date}.json`,JSON.stringify(result,null,2),'application/json')}>הורדת כל פרטי הטיול כקובץ JSON</button>
      </>}</section></div></>}<footer><span dir="ltr">TravelDNA</span><span>כל טיול מתחיל בסקרנות.</span></footer></main></>;
}
createRoot(document.getElementById('root')).render(<App/>);
