import test from 'node:test';
import assert from 'node:assert/strict';
import { itineraryText } from './export.js';

const result = {
  request: {start_date:'2026-10-01', days:1, budget:500},
  itinerary: {summary:'טיול בפריז', days:[{date:'2026-10-01',activities:[{name:'מוזיאון',description:'אמנות',start:'09:00',end:'11:00'}]}],sources:['https://example.com']},
  validation:{score:80,coverage_percent:50,issues:[],unknown:['שעות פתיחה לא אומתו']},
  guide_review:{score:80,notes:['להשאיר זמן למעבר']},
  packing:{message:'תחזית אינה זמינה',items:['נעליים'],daily:[],status:'unavailable'},
};
test('export preserves uncertainty, sources, dates and review qualification',()=>{
  const text=itineraryText(result);
  for(const value of ['2026-10-01','09:00–11:00','שעות פתיחה לא אומתו','אינן אימות עובדות','80/100','https://example.com','תחזית אינה זמינה']) assert.ok(text.includes(value));
});
test('time toggle only hides proposed times, not dates or activities',()=>{
  const text=itineraryText(result,false);
  assert.ok(!text.includes('09:00'));
  assert.ok(text.includes('2026-10-01'));
  assert.ok(text.includes('מוזיאון'));
});
test('export includes the last-year weather comparison when supplied',()=>{
  const text=itineraryText({...result, packing:{...result.packing,
    comparison:{summary:'בשנה שעברה היה גשום.'},
    historical_daily:[{date:'2025-10-01',low:9,high:15,rain_mm:7}]}});
  assert.ok(text.includes('מזג אוויר באותם תאריכים בשנה שעברה'));
  assert.ok(text.includes('2025-10-01: 9–15 מעלות, 7 מ״מ גשם'));
});
