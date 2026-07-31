/**
 * ทดสอบพฤติกรรมหน้าเว็บด้วย jsdom — ตัวกรอง, ช่องวิธีทำ, การตรวจคำตอบ, การบันทึก
 *
 * รัน:  npm i jsdom --no-save && node tools/dom_test.cjs
 * จำนวนข้อสอบอ่านจากข้อมูลจริง จึงไม่ต้องแก้เทสต์ทุกครั้งที่เพิ่มข้อสอบ
 */
const fs = require('fs');
const path = require('path');
const { JSDOM } = require('jsdom');

const HTML = path.join(__dirname, '..', 'index.html');
const html = fs.readFileSync(HTML, 'utf8');

const T = [];
const chk = (name, cond, extra = '') => T.push([cond ? 'PASS' : 'FAIL', name, String(extra)]);

function load(seed) {
  const errs = [];
  const dom = new JSDOM(html, {
    runScripts: 'dangerously',
    pretendToBeVisual: true,
    url: 'https://tkosin.github.io/funny-math/',
    beforeParse(w) {
      if (seed) w.localStorage.setItem(seed.key, JSON.stringify(seed.value));
    },
  });
  dom.virtualConsole.on('jsdomError', e => errs.push(e.message));
  return { dom, d: dom.window.document, w: dom.window, errs };
}

const { dom, d, w, errs } = load();
const $ = s => d.querySelector(s);
const $$ = s => [...d.querySelectorAll(s)];
const click = el => el.dispatchEvent(new w.Event('click'));
const type = (el, v) => { el.value = v; el.dispatchEvent(new w.Event('input')); };
const items = id => $$('#' + id + ' .fitem');
const count = el => +el.querySelector('.cnt').textContent;
const label = el => el.querySelector('.fname').textContent;
const shown = () => +($('#navCenter').textContent.match(/\/\s*(\d+)/) || [0, 0])[1];

// จำนวนข้อสอบจริงจากข้อมูลในหน้า
const TOTAL = count(items('unitList')[0]);
chk('อ่านคลังข้อสอบได้', TOTAL > 0, TOTAL);

// ---------- โครงหน้า ----------
chk('มีแผงตัวกรองด้านซ้าย', !!$('#sidebar'));
chk('แผงตัวกรองอยู่ก่อนเนื้อหา', $('.layout').children[0].id === 'sidebar');
chk('ไม่มีแถบแท็บแบบเดิมเหลืออยู่', !$('#tabs') && !$('.tabs'));
chk('ชื่อเรื่องมีจำนวนข้อตรงกับข้อมูล', $('#mainTitle').textContent.includes(String(TOTAL)),
    $('#mainTitle').textContent);

// ---------- ตัวกรอง 4 ชั้น ----------
chk('มีตัวกรองหน่วย 1 + 9', items('unitList').length === 10, items('unitList').length);
chk('มีตัวกรองระดับความยาก', items('levelList').map(label).join('/') === 'ทุกระดับ/ง่าย/กลาง/ยาก',
    items('levelList').map(label).join('/'));
chk('มีตัวกรองขอบเขตเนื้อหา',
    items('tagList').map(label).join('/') === 'ทุกขอบเขต/ม.1/ทบทวน ป.6/ต่อยอด ม.2',
    items('tagList').map(label).join('/'));
const sum = id => items(id).slice(1).reduce((a, e) => a + count(e), 0);
chk('จำนวนตามหน่วยรวมได้ครบ', sum('unitList') === TOTAL, sum('unitList'));
chk('จำนวนตามระดับรวมได้ครบ', sum('levelList') === TOTAL, sum('levelList'));
chk('จำนวนตามขอบเขตรวมได้ครบ', sum('tagList') === TOTAL, sum('tagList'));
chk('เริ่มต้นแสดงทุกข้อ', shown() === TOTAL, shown());

// เลือกหน่วย -> ประเภทเปลี่ยนตามหน่วย -> รวมกับตัวกรองอื่นแบบ AND
const u9 = items('unitList')[9];
const u9count = count(u9);
click(u9);
chk('เลือกหน่วย 9 แล้วจำนวนตรง', shown() === u9count, `${shown()} vs ${u9count}`);
chk('ประเภทข้อสอบเปลี่ยนตามหน่วยที่เลือก', items('subList').length > 1, items('subList').length);
const m1 = items('tagList')[1];
const m1count = count(m1);
click(m1);
chk('หน่วย 9 + ม.1 แคบลงแบบ AND', shown() === m1count && shown() < u9count,
    `${shown()} / ${m1count} / ${u9count}`);
click(items('levelList')[1]);
chk('เพิ่มตัวกรองระดับแล้วแคบลงอีก', shown() > 0 && shown() < m1count, shown());
click($('#resetFilterBtn'));
chk('ล้างตัวกรองกลับเป็นทุกข้อ', shown() === TOTAL, shown());

// ทุกหน่วยต้องเปิดได้และมีข้อ
for (let u = 1; u <= 9; u++) {
  click(items('unitList')[u]);
  const n = shown();
  const subs = items('subList').length - 1;
  chk(`หน่วย ${u} มีข้อสอบและมีประเภทย่อย`, n > 0 && subs > 0, `${n} ข้อ / ${subs} ประเภท`);
  chk(`หน่วย ${u} แสดงการ์ดข้อสอบได้`, !!$('#finalInput') && !!$('.qtext'), '');
}
click($('#resetFilterBtn'));

// ---------- ช่องวิธีทำหลายบรรทัด ----------
chk('เริ่มต้นมี 1 บรรทัด', $$('#workLines .work-line').length === 1);
chk('ปุ่มลบปิดใช้งานเมื่อมีบรรทัดเดียว', $$('.line-del')[0].disabled);
click($('#addLineBtn')); click($('#addLineBtn'));
chk('เพิ่มบรรทัดได้', $$('#workLines .work-line').length === 3, $$('#workLines .work-line').length);
chk('เลขบรรทัดเรียงถูก', $$('#workLines .ln').map(e => e.textContent).join('') === '1.2.3.');
const tas = () => $$('#workLines textarea');
tas().forEach((t, i) => type(t, 'ขั้น ' + (i + 1)));
tas()[1].dispatchEvent(new w.KeyboardEvent('keydown', { key: 'Enter', bubbles: true }));
chk('Enter แทรกบรรทัดใหม่', $$('#workLines .work-line').length === 4);
chk('แทรกต่อจากบรรทัดที่กด', tas()[2].value === '' && tas()[3].value === 'ขั้น 3');
tas()[2].dispatchEvent(new w.KeyboardEvent('keydown', { key: 'Backspace', bubbles: true }));
chk('Backspace ในบรรทัดว่างลบบรรทัด', $$('#workLines .work-line').length === 3);
click($$('.line-del')[2]);
chk('ปุ่ม × ลบบรรทัด', $$('#workLines .work-line').length === 2);

// ---------- ตรวจคำตอบ ----------
const res = () => $('#checkResult');
click($('#checkBtn'));
chk('ยังไม่กรอกแล้วกดตรวจ -> เตือน', res().className.includes('show'), res().textContent);
const key = w.QUESTIONS ? null : null;
type($('#finalInput'), 'ค่าที่ผิดแน่นอน 99999');
click($('#checkBtn'));
chk('คำตอบผิด -> ไม่ถูก', /\b(no|manual)\b/.test(res().className), res().className);
chk('คำตอบผิดไม่ติ๊กว่าทำแล้ว', !$('#doneCheck').checked);

// ข้อแรกของหน่วย 1 เฉลยเป็นตัวเลข ใช้ตรวจเส้นทาง "ถูกต้อง"
const firstAnswer = d.querySelector('.answer').textContent.replace('เฉลย:', '').trim();
type($('#finalInput'), firstAnswer);
chk('พิมพ์ใหม่แล้วผลตรวจหาย', !res().className.includes('show'));
click($('#checkBtn'));
chk('ตอบถูก -> ถูกต้อง', res().className.includes('ok'), `${firstAnswer} -> ${res().className}`);
chk('ตอบถูกติ๊กว่าทำแล้วให้เอง', $('#doneCheck').checked);
chk('ความก้าวหน้านับให้', $('#progressLabel').textContent.includes('ทำแล้ว 1'),
    $('#progressLabel').textContent);

// ---------- คงข้อมูลเมื่อสลับข้อ ----------
click($('#nextBtn'));
chk('ข้อใหม่เริ่มจากบรรทัดว่าง', $$('#workLines .work-line').length === 1 && tas()[0].value === '');
click($('#prevBtn'));
chk('กลับมาแล้ววิธีทำยังอยู่', $$('#workLines .work-line').length === 2, $$('#workLines .work-line').length);
chk('กลับมาแล้วข้อความยังอยู่', tas()[0].value === 'ขั้น 1', tas()[0].value);
chk('กลับมาแล้วคำตอบยังอยู่', $('#finalInput').value === firstAnswer);
chk('กลับมาแล้วผลตรวจยังอยู่', res().className.includes('ok'));

// ---------- บันทึกลง localStorage ----------
const keys = Object.keys(w.localStorage);
chk('บันทึกด้วยคีย์ที่มีเลขเวอร์ชัน', keys.some(k => /^funnymath-m1-v\d+$/.test(k)), keys.join());
const saved = JSON.parse(w.localStorage.getItem(keys.find(k => k.startsWith('funnymath'))) || '{}');
chk('บันทึกข้อที่ทำแล้วและคำตอบ',
    Array.isArray(saved.done) && saved.done.length === 1 && !!saved.finalAns,
    JSON.stringify(saved).slice(0, 90));

// ---------- เฉลยล็อกด้วยรหัสผ่าน ----------
click($('#revealBtn'));
chk('กดดูเฉลยแล้วขอรหัสผ่าน', $('#pwOverlay').classList.contains('show'));
$('#pwInput').value = 'ผิด';
click($('#pwConfirmBtn'));
chk('รหัสผิดไม่เปิดเฉลย', !$('.answer').classList.contains('show'));
$('#pwInput').value = '2569';
click($('#pwConfirmBtn'));
chk('รหัสถูกเปิดเฉลย', $('.answer').classList.contains('show'));

// ---------- โหลดข้อมูลที่บันทึกไว้กลับมาได้ ----------
{
  const key = Object.keys(w.localStorage).find(k => k.startsWith('funnymath'));
  const r = load({ key, value: { done: [0, 5], work: { 0: ['a', 'b', 'c'] }, finalAns: { 0: '42' }, checked: {} } });
  const rd = s => r.d.querySelector(s);
  chk('รีเฟรชแล้วกู้วิธีทำกลับมา', r.d.querySelectorAll('#workLines .work-line').length === 3,
      r.d.querySelectorAll('#workLines .work-line').length);
  chk('รีเฟรชแล้วกู้คำตอบกลับมา', rd('#finalInput').value === '42', rd('#finalInput').value);
  chk('รีเฟรชแล้วกู้จำนวนข้อที่ทำแล้ว', rd('#progressLabel').textContent.includes('ทำแล้ว 2'),
      rd('#progressLabel').textContent);
  chk('ข้อมูลที่บันทึกเสียหายก็ยังเปิดหน้าได้',
      !!load({ key, value: 'ไม่ใช่ JSON' }).d.querySelector('#finalInput'));
}

// ---------- ผลลัพธ์ ----------
const failed = T.filter(t => t[0] === 'FAIL');
console.log(T.map(([s, n, e]) => `${s}  ${n}${s === 'FAIL' ? '   << ' + e : ''}`).join('\n'));
console.log(`\n${T.length - failed.length}/${T.length} ผ่าน`);
if (errs.length) console.log('JS ERRORS:\n' + errs.join('\n'));
process.exit(failed.length || errs.length ? 1 : 0);
