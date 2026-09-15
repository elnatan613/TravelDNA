export function itineraryText(result, showHours = true) {
  const t = result.itinerary, v = result.validation;
  return ['TravelDNA', `${result.request.start_date} · ${result.request.days} ימים · ${result.request.budget} דולר`, t.summary, '',
    ...t.days.flatMap(d => [`יום ${d.date}`, ...d.activities.map(a => `${showHours ? `${a.start}–${a.end} | ` : ''}${a.name}\n${a.description}`), '']),
    'בדיקת היתכנות', `ציון היתכנות מחושב: ${v.score}/100`, `כיסוי בדיקות: ${v.coverage_percent}%`, ...v.issues, ...v.unknown,
    'המלצות מדריך — הצעות מודל, אינן אימות עובדות',
    ...(result.guide_review ? result.guide_review.notes : ['ההמלצות אינן זמינות']),
    'מה לארוז', result.packing.message, ...result.packing.items,
    ...result.packing.daily.map(d => `${d.date}: ${d.low}–${d.high} מעלות, ${d.rain}% סיכוי לגשם`),
    ...(result.packing.comparison ? ['מזג אוויר באותם תאריכים בשנה שעברה', result.packing.comparison.summary,
      ...(result.packing.historical_daily || []).map(d => `${d.date}: ${d.low}–${d.high} מעלות, ${d.rain_mm} מ״מ גשם`)] : []),
    'מקורות', ...t.sources, ...(result.packing.status === 'forecast' ? [result.packing.source] : [])].join('\n');
}

export function download(name, text, type) {
  const url = URL.createObjectURL(new Blob([type.startsWith('text/') ? '\ufeff' : '', text], {type}));
  const link = document.createElement('a');
  link.href = url; link.download = name;
  document.body.appendChild(link); link.click(); link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 10000);
}
