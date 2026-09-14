export function itineraryText(result, showHours = true) {
  const t = result.itinerary, v = result.validation;
  return ['TravelDNA', `${result.request.start_date} · ${result.request.days} ימים · ${result.request.budget} דולר`, t.summary, '',
    ...t.days.flatMap(d => [`יום ${d.date}`, ...d.activities.map(a => `${showHours ? `${a.start}–${a.end} | ` : ''}${a.name}\n${a.description}`), '']),
    'בדיקת היתכנות', `כיסוי בדיקות: ${v.coverage_percent}%`, ...v.issues, ...v.unknown,
    'ביקורת מדריך — הערכת מודל, אינה אימות עובדות',
    ...(result.guide_review ? [`ציון התרשמות: ${result.guide_review.score}/100`, ...result.guide_review.notes] : ['הביקורת אינה זמינה']),
    'מה לארוז', result.packing.message, ...result.packing.items,
    ...result.packing.daily.map(d => `${d.date}: ${d.low}–${d.high} מעלות, ${d.rain}% סיכוי לגשם`),
    'מקורות', ...t.sources, ...(result.packing.status === 'forecast' ? [result.packing.source] : [])].join('\n');
}

export function download(name, text, type) {
  const url = URL.createObjectURL(new Blob([type.startsWith('text/') ? '\ufeff' : '', text], {type}));
  const link = document.createElement('a');
  link.href = url; link.download = name;
  document.body.appendChild(link); link.click(); link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 10000);
}
