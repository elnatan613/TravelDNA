export const DRAFT_KEY = 'traveldna-experiences-v1';
export const PARTIES = {solo:'לבד', couple:'בזוג', friends:'עם חברים', family:'עם המשפחה'};
export const CARD_IDS = ['city','picnic','museum','food','hike','music','nightlife','workshop','free-time','full-day','shopping','beach'];
export const freshDraft = () => ({version:1, stage:'party', index:0, party:'', children:null, childAges:'', choices:{}, notes:''});

export function restoreDraft(raw) {
  try {
    const d = JSON.parse(raw);
    if (d?.version !== 1 || !['party','cards','notes'].includes(d.stage) || !Number.isInteger(d.index) || d.index < 0 || d.index > 12) return freshDraft();
    if (d.stage === 'cards' && d.index === 12) return freshDraft();
    if (d.party !== '' && !Object.hasOwn(PARTIES,d.party)) return freshDraft();
    if (!d.choices || typeof d.choices !== 'object' || Object.entries(d.choices).some(([id,v]) => !CARD_IDS.includes(id) || !['yes','no','skip'].includes(v))) return freshDraft();
    if (d.stage !== 'party' && !d.party) return freshDraft();
    if (CARD_IDS.slice(0,d.index).some(id=>!d.choices[id]) || (d.stage==='notes' && CARD_IDS.some(id=>!d.choices[id]))) return freshDraft();
    return {...freshDraft(), ...d, notes:typeof d.notes==='string'?d.notes.slice(0,3000):'', childAges:typeof d.childAges==='string'?d.childAges.slice(0,60):'', children:typeof d.children==='boolean'?d.children:null};
  } catch { return freshDraft(); }
}

export function vote(draft, id, choice) {
  if (draft.stage !== 'cards' || CARD_IDS[draft.index] !== id || !['yes','no','skip'].includes(choice)) return draft;
  const index = draft.index+1;
  return {...draft, choices:{...draft.choices,[id]:choice}, index, stage:index===12?'notes':'cards'};
}

export function chooseParty(draft, party) {
  return {...draft, party, ...(party !== 'family' ? {children:null,childAges:''} : {})};
}

export function parseAges(text) {
  if (!text.trim()) return [];
  const values=text.trim().split(/[,،\s]+/);
  if (values.length>12 || values.some(v=>!/^\d{1,2}$/.test(v) || Number(v)>17)) throw new Error('כתבו גילאים בין 0 ל־17, מופרדים בפסיק. אפשר גם להשאיר ריק.');
  return values.map(Number);
}

export function surveyPayload(draft) {
  return {party:draft.party, children:draft.party==='family'?draft.children:null,
    child_ages:draft.party==='family'&&draft.children===true?parseAges(draft.childAges):[], choices:draft.choices, notes:draft.notes};
}

export function inferredPace(choices) {
  if (choices['free-time']==='yes' && choices['full-day']!=='yes') return 'relaxed';
  if (choices['full-day']==='yes' && choices['free-time']!=='yes') return 'busy';
  return 'balanced';
}
