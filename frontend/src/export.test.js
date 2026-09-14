import test from 'node:test';
import assert from 'node:assert/strict';
import { itineraryText } from './export.js';

const result = {
  request: {start_date:'2026-10-01', days:1, budget:500},
  itinerary: {summary:'טיול בפריז', days:[{date:'2026-10-01',activities:[{name:'מוזיאון',description:'אמנות',start:'09:00',end:'11:00'}]}],sources:['https://example.com']},
  validation:{coverage_percent:50,issues:[],unknown:['שעות פתיחה לא אומתו']},
  guide_review:{score:80,notes:['להשאיר זמן למעבר']},
  packing:{message:'תחזית אינה זמינה',items:['נעליים'],daily:[],status:'unavailable'},
};
test('export preserves uncertainty, sources, dates and review qualification',()=>{
  const text=itineraryText(result);
  for(const value of ['2026-10-01','09:00–11:00','שעות פתיחה לא אומתו','אינה אימות עובדות','80/100','https://example.com','תחזית אינה זמינה']) assert.ok(text.includes(value));
});
test('time toggle only hides proposed times, not dates or activities',()=>{
  const text=itineraryText(result,false);
  assert.ok(!text.includes('09:00'));
  assert.ok(text.includes('2026-10-01'));
  assert.ok(text.includes('מוזיאון'));
});
