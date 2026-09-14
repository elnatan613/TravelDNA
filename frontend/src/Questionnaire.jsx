import React, {useEffect, useRef, useState} from 'react';
import cards from '../../data/experience_cards.json';
import {PARTIES, chooseParty, parseAges, vote} from './survey-state.js';
import './questionnaire.css';

function PartyIcon({party}) {
  const count={solo:1,couple:2,friends:3,family:3}[party];
  return <svg viewBox="0 0 72 48" fill="none" aria-hidden="true">{Array.from({length:count},(_,i)=>{
    const x=36+(i-(count-1)/2)*20, small=party==='family'&&i===2;
    return <g key={i} transform={`translate(${x},${small?10:0}) scale(${small ? 0.72 : 1})`}><circle cy="12" r="6"/><path d="M-10 37v-6c0-6 4-10 10-10s10 4 10 10v6"/></g>;
  })}</svg>;
}

export default function Questionnaire({draft, onChange, onFinish, busy, error}) {
  const [offset,setOffset]=useState(0), [localError,setLocalError]=useState('');
  const drag=useRef(null), heading=useRef(null);
  const card=cards[draft.index];
  useEffect(()=>{ heading.current?.focus({preventScroll:true}); },[draft.stage]);
  useEffect(()=>{
    const next=cards[draft.index+1];
    if(next){const image=new Image();image.src=`/experiences/${next.id}.webp`;}
  },[draft.index]);
  function answer(value) {
    if(!card || busy)return;
    setOffset(0); drag.current=null;
    onChange(prev=>vote(prev,card.id,value));
  }
  function startCards() {
    try {if(draft.party==='family'&&draft.children===true)parseAges(draft.childAges);}
    catch(e){setLocalError(e.message);return;}
    setLocalError('');
    onChange(prev=>({...prev,stage:'cards',index:Math.min(prev.index,11)}));
  }
  function back() {
    setOffset(0); drag.current=null;
    onChange(prev=>({...prev,stage:prev.index===0?'party':'cards',index:Math.max(0,prev.index-1)}));
  }
  function pointerDown(e) {
    if(!e.isPrimary || e.button!==0)return;
    drag.current={x:e.clientX,y:e.clientY,id:e.pointerId};
    e.currentTarget.setPointerCapture(e.pointerId);
  }
  function pointerMove(e) {
    if(drag.current?.id!==e.pointerId)return;
    const dx=e.clientX-drag.current.x,dy=e.clientY-drag.current.y;
    if(Math.abs(dx)>Math.abs(dy))setOffset(dx);
  }
  function pointerUp(e) {
    if(drag.current?.id!==e.pointerId)return;
    const dx=e.clientX-drag.current.x,dy=e.clientY-drag.current.y;
    drag.current=null;setOffset(0);
    if(Math.abs(dx)>=75&&Math.abs(dx)>Math.abs(dy)*1.3)answer(dx>0?'yes':'no');
  }
  const stageNumber={party:1,cards:2,notes:3}[draft.stage];
  return <section className={`questionnaire questionnaire-${draft.stage}`}>
    <nav className="journey-steps" aria-label="התקדמות השאלון">{['עם מי נוסעים','בוחרים חוויות','משהו להוסיף'].map((label,i)=><span key={label} className={stageNumber===i+1?'current':stageNumber>i+1?'done':''} aria-current={stageNumber===i+1?'step':undefined}><b>{stageNumber>i+1?'✓':`0${i+1}`}</b>{label}</span>)}</nav>
    {draft.stage==='party' && <div className="welcome-layout"><div className="welcome-copy"><p className="eyebrow">טיול אחד. בדיוק כמו שבא לכם.</p><h1 ref={heading} tabIndex={-1}>לפני שבוחרים לאן,<br/><em>עם מי נוסעים?</em></h1><p>עוד רגע תבחרו את החוויות שבא לכם לשלב.<br/>נתחיל באנשים שיהיו חלק מהסיפור.</p><div className="party-options" role="group" aria-label="עם מי נוסעים">{Object.entries(PARTIES).map(([id,label])=><button key={id} className={draft.party===id?'chosen':''} aria-pressed={draft.party===id} onClick={()=>{setLocalError('');onChange(prev=>chooseParty(prev,id));}}><PartyIcon party={id}/><span>{label}</span><i aria-hidden="true">{draft.party===id?'✓':'+'}</i></button>)}</div>
      {draft.party==='family' && <div className="children-fields"><p>מצטרפים ילדים? <small>אפשר לדלג</small></p><div className="child-options">{[[true,'כן'],[false,'לא'],[null,'דלגו']].map(([value,label])=><button key={label} aria-pressed={draft.children===value} className={draft.children===value?'chosen':''} onClick={()=>onChange(prev=>({...prev,children:value,childAges:value===true?prev.childAges:''}))}>{label}</button>)}</div>{draft.children===true&&<label>באילו גילאים? <small>אופציונלי</small><input value={draft.childAges} maxLength={60} placeholder="למשל: 4, 8, 12" onChange={e=>onChange(prev=>({...prev,childAges:e.target.value}))}/></label>}</div>}
      {localError&&<p className="error" role="alert">{localError}</p>}<button className="primary welcome-next" disabled={!draft.party} onClick={startCards}>בואו נבחר חוויות <span>←</span></button><p className="onboarding-footnote">12 חוויות · בלי תשובות נכונות או לא נכונות</p></div>
      <div className="welcome-art" aria-hidden="true"><div className="photo-back"><img src="/experiences/picnic.webp" alt=""/></div><div className="photo-front"><img src="/experiences/city.webp" alt=""/><span>רגעים ששווה לצאת בשבילם.</span></div><div className="art-stamp">YOUR TRIP<br/><b>YOUR WAY</b><span>✳</span></div></div></div>}
    {draft.stage==='cards'&&card&&<div className="swipe-layout"><div className="swipe-intro"><p className="eyebrow">מכירים את הטיול שלכם</p><h1 ref={heading} tabIndex={-1}>מה בא לכם<br/><em>לשלב הפעם?</em></h1><p>דמיינו את עצמכם שם.<br/>מתאים לטיול הזה? החליקו ימינה.<br/>פחות הפעם? החליקו שמאלה.</p><div className="swipe-key"><span>♡ כן, מתאים</span><span>× לא הפעם</span></div><p className="muted">אפשר לאהוב גם וגם.<br/>אנחנו נמצא את הדרך לשלב.</p><button className="text-button" onClick={back}>{draft.index===0?'חזרה להרכב הנוסעים':'↶ חזרה לכרטיס הקודם'}</button></div>
      <div className="swipe-area"><div className="card-progress"><span>החוויה הבאה שלכם</span><span dir="ltr" aria-live="polite">{draft.index+1} / {cards.length}</span></div><div className="progress-track" role="progressbar" aria-label="חוויות שנענו" aria-valuemin={0} aria-valuemax={12} aria-valuenow={draft.index}><span style={{width:`${draft.index/12*100}%`}}/></div>
      <div className="deck"><article className="experience-card" tabIndex={0} aria-label={`${card.title}. חץ ימינה: כן. חץ שמאלה: לא. מקש רווח: דילוג.`} onKeyDown={e=>{if(['ArrowRight','ArrowLeft',' '].includes(e.key)&&!e.repeat){e.preventDefault();answer(e.key==='ArrowRight'?'yes':e.key==='ArrowLeft'?'no':'skip');}}} onPointerDown={pointerDown} onPointerMove={pointerMove} onPointerUp={pointerUp} onPointerCancel={()=>{drag.current=null;setOffset(0);}} style={{transform:`translateX(${Math.max(-160,Math.min(160,offset))}px) rotate(${offset/22}deg)`}}>
        <img src={`/experiences/${card.id}.webp`} alt={card.alt} draggable="false" fetchPriority="high"/><div className="experience-shade"/><span className="experience-category">{card.category}</span>{Math.abs(offset)>25&&<span className={`swipe-stamp ${offset>0?'yes':'no'}`}>{offset>0?'כן, מתאים':'לא הפעם'}</span>}<div className="experience-caption"><span>חוויה {String(draft.index+1).padStart(2,'0')}</span><h2 aria-live="polite">{card.title}</h2></div>
      </article></div><div className="swipe-actions" dir="ltr"><button className="vote-no" onClick={()=>answer('no')} aria-label="לא הפעם"><span aria-hidden="true">×</span><small>לא הפעם</small></button><button className="vote-skip" onClick={()=>answer('skip')} aria-label="דלגו על החוויה"><span aria-hidden="true">↷</span><small>דלגו</small></button><button className="vote-yes" onClick={()=>answer('yes')} aria-label="כן, מתאים"><span aria-hidden="true">♡</span><small>כן, מתאים</small></button></div><p className="image-note">תמונות להמחשת החוויות · נוצרו ב־AI</p></div></div>}
    {draft.stage==='notes'&&<div className="notes-panel card"><span className="notes-spark" aria-hidden="true">✳</span><p className="eyebrow">מקום גם לפרטים הקטנים</p><h1 ref={heading} tabIndex={-1}>משהו נוסף שחשוב לכם בטיול?</h1><p className="muted">כל מה שלא נכנס לתמונות. אפשר גם להמשיך בלי להוסיף.</p><label className="notes-label" htmlFor="trip-notes">הערות לטיול <small>אופציונלי</small></label><textarea id="trip-notes" disabled={busy} rows={5} maxLength={3000} value={draft.notes} placeholder="חשובה לנו כשרות, מעדיפים מעט הליכה, רוצים לבקר במקום מסוים או להימנע ממשהו…" onChange={e=>onChange(prev=>({...prev,notes:e.target.value}))}/><small className="notes-count" dir="ltr">{draft.notes.length} / 3000</small>{error&&<p className="error" role="alert">{error}</p>}<button className="primary wide" disabled={busy} onClick={()=>onFinish(false)}>{busy?'מוצאים את הכיוון שלכם…':'מצאו לנו יעד מתאים ←'}</button><button className="secondary wide" disabled={busy} onClick={()=>onFinish(true)}>כבר בחרנו יעד — ממשיכים למסלול</button><button className="text-button" disabled={busy} onClick={back}>↶ חזרה לכרטיס האחרון</button></div>}
  </section>;
}
