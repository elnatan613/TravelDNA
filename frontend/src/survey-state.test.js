import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync,existsSync} from 'node:fs';
import {freshDraft, restoreDraft, vote, chooseParty, surveyPayload, inferredPace, CARD_IDS} from './survey-state.js';

const start=()=>({...freshDraft(),party:'couple',stage:'cards'});
test('twelve decisions lead directly to notes and retain skips',()=>{
  let state=start();
  for(const id of CARD_IDS)state=vote(state,id,'skip');
  assert.equal(state.stage,'notes');
  assert.equal(Object.keys(surveyPayload(state).choices).length,12);
  assert.ok(Object.values(state.choices).every(v=>v==='skip'));
});
test('undo and replacement changes one answer without losing later answers',()=>{
  let state=vote(vote(start(),'city','yes'),'picnic','no');
  state={...state,index:0};
  state=vote(state,'city','no');
  assert.equal(state.choices.city,'no');
  assert.equal(state.choices.picnic,'no');
  assert.equal(state.index,1);
});
test('stale gestures cannot vote on the next card',()=>{
  const state=vote(start(),'city','yes');
  assert.deepEqual(vote(state,'city','no'),state);
});
test('draft survives refresh while malformed session data is ignored',()=>{
  const state=vote(start(),'city','yes');
  assert.deepEqual(restoreDraft(JSON.stringify(state)),state);
  assert.deepEqual(restoreDraft('{bad'),freshDraft());
  assert.deepEqual(restoreDraft(JSON.stringify({...state,index:11})),freshDraft());
});
test('switching away from family clears child information',()=>{
  const state=chooseParty({...start(),party:'family',children:true,childAges:'4, 8'},'friends');
  assert.equal(state.children,null);
  assert.deepEqual(surveyPayload(state).child_ages,[]);
});
test('optional child ages accept zero and reject invalid ages',()=>{
  assert.deepEqual(surveyPayload({...start(),party:'family',children:true,childAges:'0, 8'}).child_ages,[0,8]);
  assert.throws(()=>surveyPayload({...start(),party:'family',children:true,childAges:'-3, 20'}));
});
test('mixed pace is balanced and a skipped card is not a dislike',()=>{
  assert.equal(inferredPace({'free-time':'yes','full-day':'yes'}),'balanced');
  assert.equal(inferredPace({'free-time':'skip','full-day':'skip'}),'balanced');
  assert.equal(inferredPace({'free-time':'yes','full-day':'no'}),'relaxed');
});
test('shared deck order and all production images exist',()=>{
  const cards=JSON.parse(readFileSync(new URL('../../data/experience_cards.json',import.meta.url),'utf8'));
  assert.deepEqual(cards.map(c=>c.id),CARD_IDS);
  for(const card of cards)assert.ok(existsSync(new URL(`../public/experiences/${card.id}.webp`,import.meta.url)),card.id);
});
