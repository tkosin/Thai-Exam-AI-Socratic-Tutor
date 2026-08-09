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
    url: 'https://tkosin.github.io/math-is-fun/',
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

// จำนวนข้อสอบของ "วิชาที่เลือกอยู่" (ไม่ใช่ทั้งคลัง — คลังมีหลายวิชา)
const TOTAL = count(items('unitList')[0]);
chk('อ่านคลังข้อสอบได้', TOTAL > 0, TOTAL);

// ---------- โครงหน้า ----------
chk('มีแผงตัวกรองด้านซ้าย', !!$('#sidebar'));
chk('แผงตัวกรองอยู่ก่อนเนื้อหา', $('.layout').children[0].id === 'sidebar');
chk('ไม่มีแถบแท็บแบบเดิมเหลืออยู่', !$('#tabs') && !$('.tabs'));
chk('ชื่อเรื่องมีจำนวนข้อตรงกับข้อมูล', $('#mainTitle').textContent.includes(String(TOTAL)),
    $('#mainTitle').textContent);

// ---------- ตัวกรองวิชา (วิชา + ระดับชั้น) ----------
const courses = () => items('courseList');
chk('มีตัวกรองวิชา', courses().length >= 2, courses().length + ' วิชา');
chk('เลือกวิชาแรกไว้ตั้งแต่เปิดหน้า', courses()[0].classList.contains('active'),
    courses().map(label).join(' / '));
chk('ตัวกรองวิชาไม่มีตัวเลือก "ทุกวิชา"',
    courses().every(e => !/ทุกวิชา/.test(label(e))), courses().map(label).join(' / '));
chk('จำนวนของทุกวิชารวมกันมากกว่าวิชาเดียว',
    courses().reduce((a, e) => a + count(e), 0) > TOTAL,
    courses().map(e => `${label(e)}:${count(e)}`).join(' · '));
chk('ชื่อเรื่องตรงกับวิชาที่เลือก', $('#mainTitle').textContent.includes(label(courses()[0])),
    $('#mainTitle').textContent);
chk('หัวกลุ่มวิชาแสดงวิชาที่เลือกอยู่เสมอ',
    !!d.querySelector('#group-course .fhead .fsel'),
    d.querySelector('#group-course .fhead').textContent.trim());

// ---------- ตัวกรอง 4 ชั้นภายในวิชา ----------
const UNITS = items('unitList').length - 1;      // ไม่นับปุ่ม "ทุกหน่วย"
chk('มีตัวกรองหน่วยครบ (อ่านจากข้อมูล)', UNITS >= 9, UNITS + ' หน่วย');
chk('ทุกปุ่มหน่วยมีเลขหน่วยกำกับ',
    items('unitList').slice(1).every(e => e.querySelector('.unum')), '');
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
for (let u = 1; u <= UNITS; u++) {
  click(items('unitList')[u]);
  const n = shown();
  const subs = items('subList').length - 1;
  chk(`หน่วย ${u} มีข้อสอบและมีประเภทย่อย`, n > 0 && subs > 0, `${n} ข้อ / ${subs} ประเภท`);
  chk(`หน่วย ${u} แสดงการ์ดข้อสอบได้`, !!$('#finalInput') && !!$('.qtext'), '');
}
click($('#resetFilterBtn'));

// ---------- กลุ่มตัวกรองพับ/กางได้ ----------
const head = k => d.querySelector('#group-' + k + ' .fhead');
const listOf = k => d.querySelector('#group-' + k + ' .flist');
const isOpen = k => !d.querySelector('#group-' + k).classList.contains('collapsed');
chk('หัวกลุ่มทุกกลุ่มเป็นปุ่มกดได้', ['unit', 'sub', 'level', 'tag']
    .every(k => head(k) && head(k).tagName === 'BUTTON'), '');
chk('หัวกลุ่มบอกสถานะด้วย aria-expanded', head('unit').getAttribute('aria-expanded') === 'true'
    && head('level').getAttribute('aria-expanded') === 'false',
    head('unit').getAttribute('aria-expanded') + '/' + head('level').getAttribute('aria-expanded'));
chk('หัวกลุ่มชี้ไปยังรายการที่ควบคุม',
    head('sub').getAttribute('aria-controls') === listOf('sub').id, '');
chk('ค่าเริ่มต้น: หน่วยและประเภทกางอยู่', isOpen('unit') && isOpen('sub'), '');
chk('ค่าเริ่มต้น: ระดับและขอบเขตพับอยู่', !isOpen('level') && !isOpen('tag'), '');
chk('กลุ่มที่พับไม่แสดงรายการ', !!d.querySelector('#group-level.collapsed .flist'), '');
click(head('level'));
chk('กดหัวกลุ่มแล้วกางออก', isOpen('level') && head('level').getAttribute('aria-expanded') === 'true', '');
chk('กางแล้วเห็นรายการครบ', items('levelList').length === 4, items('levelList').length);
click(head('unit'));
chk('กดอีกกลุ่มแล้วพับได้', !isOpen('unit'), '');
chk('พับกลุ่มหน่วยไม่กระทบกลุ่มอื่น', isOpen('sub') && isOpen('level'), '');
// กลุ่มที่พับอยู่ต้องยังบอกได้ว่ามีตัวกรองทำงานอยู่
click(head('unit'));
click(items('unitList')[1]);
click(head('unit'));
chk('กลุ่มที่พับแสดงค่าที่เลือกไว้', !isOpen('unit') && !!head('unit').querySelector('.fsel'),
    head('unit').textContent.trim());
click($('#resetFilterBtn'));
chk('ล้างตัวกรองแล้วป้ายค่าที่เลือกหายไป', !head('unit').querySelector('.fsel'), '');
chk('ล้างตัวกรองไม่ไปกางกลุ่มที่พับไว้', !isOpen('unit'), '');
click(head('unit'));   // กลับสู่สภาพเดิมก่อนทดสอบส่วนอื่น

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
const PROGRESS = /^funnymath-m1-v\d+$/;          // คีย์ความก้าวหน้า (แยกจากคีย์ความชอบส่วนตัว)
const keys = Object.keys(w.localStorage);
chk('บันทึกด้วยคีย์ที่มีเลขเวอร์ชัน', keys.some(k => PROGRESS.test(k)), keys.join());
chk('ความชอบส่วนตัวเก็บแยกคีย์', keys.some(k => k === 'funnymath-ui-v1'), keys.join());
const saved = JSON.parse(w.localStorage.getItem(keys.find(k => PROGRESS.test(k))) || '{}');
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
  const key = Object.keys(w.localStorage).find(k => PROGRESS.test(k));
  const r = load({ key, value: { done: [0, 5], work: { 0: ['a', 'b', 'c'] }, finalAns: { 0: '42' }, checked: {} } });
  const rd = s => r.d.querySelector(s);
  chk('รีเฟรชแล้วกู้วิธีทำกลับมา', r.d.querySelectorAll('#workLines .work-line').length === 3,
      r.d.querySelectorAll('#workLines .work-line').length);
  chk('รีเฟรชแล้วกู้คำตอบกลับมา', rd('#finalInput').value === '42', rd('#finalInput').value);
  chk('รีเฟรชแล้วกู้จำนวนข้อที่ทำแล้ว', rd('#progressLabel').textContent.includes('ทำแล้ว 2'),
      rd('#progressLabel').textContent);
  chk('ข้อมูลที่บันทึกเสียหายก็ยังเปิดหน้าได้',
      !!load({ key, value: 'ไม่ใช่ JSON' }).d.querySelector('#finalInput'));

  // การพับ/กางกลุ่มตัวกรองต้องอยู่ข้ามการรีเฟรช และไม่พังเมื่อข้อมูลเสียหาย
  const ui = load({ key: 'funnymath-ui-v1', value: { collapsed: { unit: true, sub: true, level: false, tag: false } } });
  const cls = k => r2 => r2.d.querySelector('#group-' + k).classList.contains('collapsed');
  chk('รีเฟรชแล้วจำการพับ/กางไว้',
      cls('unit')(ui) && cls('sub')(ui) && !cls('level')(ui) && !cls('tag')(ui), '');
  const uiBad = load({ key: 'funnymath-ui-v1', value: 'ไม่ใช่ JSON' });
  chk('ความชอบที่เสียหายกลับไปใช้ค่าเริ่มต้น',
      !cls('unit')(uiBad) && cls('level')(uiBad), '');
}

// ---------- แผงตัวกรอง: ซ่อนไว้เป็นค่าเริ่มต้น กาง/พับได้ทุกขนาดจอ ----------
{
  const r = load();
  const rd = s => r.d.querySelector(s);
  const rclick = el => el.dispatchEvent(new r.w.Event('click'));
  const isOpen = () => rd('#sidebar').classList.contains('open');
  const aria = () => rd('#filterToggle').getAttribute('aria-expanded');

  chk('เริ่มต้นแผงตัวกรองถูกซ่อนไว้', !isOpen() && aria() === 'false', aria());
  chk('ปุ่มตัวกรองไม่ถูกซ่อนด้วย CSS ฐาน (เห็นได้ทุกขนาดจอ)',
      !/\.filter-toggle\s*\{\s*display\s*:\s*none/.test(html), '');
  chk('มีปุ่มปิดอยู่ในแผง', !!rd('#sidebarCloseBtn'));

  rclick(rd('#filterToggle'));
  chk('กดปุ่มแล้วแผงกางออก', isOpen() && aria() === 'true', aria());
  rclick(rd('#filterToggle'));
  chk('กดปุ่มซ้ำแล้วพับเก็บ', !isOpen() && aria() === 'false', aria());
  rclick(rd('#filterToggle'));
  rclick(rd('#sidebarCloseBtn'));
  chk('กดปิดในแผงแล้วพับเก็บ', !isOpen() && aria() === 'false', aria());

  // สถานะกาง/พับของแผงเป็นความชอบส่วนตัว ต้องอยู่ข้ามการรีเฟรช
  rclick(rd('#filterToggle'));
  const ui = JSON.parse(r.w.localStorage.getItem('funnymath-ui-v1') || '{}');
  chk('บันทึกสถานะกาง/พับของแผง', ui.sidebarOpen === true, JSON.stringify(ui));
  chk('รีเฟรชแล้วจำว่าแผงกางอยู่',
      load({ key: 'funnymath-ui-v1', value: { sidebarOpen: true } })
        .d.querySelector('#sidebar').classList.contains('open'));

  // แผงถูกซ่อนแล้วตัวกรองต้องไม่หายเงียบ ๆ — ปุ่มบอกจำนวนตัวกรองที่ใช้อยู่
  const badge = () => rd('#filterBadge').textContent;
  chk('ยังไม่กรองอะไร ปุ่มไม่มีตัวเลข', badge() === '', badge());
  rclick(r.d.querySelectorAll('#unitList .fitem')[1]);      // เลือกหน่วยที่ 1
  chk('เลือกตัวกรองแล้วปุ่มขึ้นจำนวน', badge() === '1', badge());
  rclick(r.d.querySelectorAll('#levelList .fitem')[1]);     // + ระดับง่าย
  chk('กรองสองชั้นแล้วนับเป็น 2', badge() === '2', badge());
  rclick(rd('#resetFilterBtn'));
  chk('ล้างตัวกรองแล้วตัวเลขหาย', badge() === '', badge());
}

// ---------- สลับวิชา ----------
{
  const r = load();
  const rd = s => r.d.querySelector(s);
  const rall = s => [...r.d.querySelectorAll(s)];
  const rclick = el => el.dispatchEvent(new r.w.Event('click'));
  const cItems = () => rall('#courseList .fitem');
  const uItems = () => rall('#unitList .fitem');
  const cnt = el => +el.querySelector('.cnt').textContent;
  const name = el => el.querySelector('.fname').textContent;
  const showing = () => +(rd('#navCenter').textContent.match(/\/\s*(\d+)/) || [0, 0])[1];

  const first = cItems()[0], second = cItems()[1];
  const firstUnits = uItems().map(name).join('|');
  const secondCount = cnt(second);

  // เลือกตัวกรองในวิชาแรกไว้ก่อน เพื่อดูว่าสลับวิชาแล้วถูกล้างจริง
  rclick(uItems()[1]);
  rclick(rall('#levelList .fitem')[1]);
  chk('ก่อนสลับวิชามีตัวกรองทำงานอยู่', rd('#filterBadge').textContent === '2',
      rd('#filterBadge').textContent);

  rclick(second);
  chk('สลับวิชาแล้วจำนวนข้อตรงกับวิชาใหม่', showing() === secondCount,
      `${showing()} vs ${secondCount}`);
  chk('สลับวิชาแล้วล้างตัวกรองของวิชาเดิม', rd('#filterBadge').textContent === '',
      rd('#filterBadge').textContent);
  chk('สลับวิชาแล้วรายการหน่วยเปลี่ยนตาม', uItems().map(name).join('|') !== firstUnits,
      uItems().map(name).join('|').slice(0, 60));
  chk('สลับวิชาแล้วชื่อเรื่องเปลี่ยนตาม', rd('#mainTitle').textContent.includes(name(second)),
      rd('#mainTitle').textContent);
  chk('เลขข้อเริ่มนับใหม่ในแต่ละวิชา', rd('.qnum-big').textContent.trim() === 'ข้อที่ 1',
      rd('.qnum-big').textContent);
  chk('ทุกวิชามีเพียงวิชาเดียวที่ถูกเลือก',
      cItems().filter(e => e.classList.contains('active')).length === 1, '');

  // ล้างตัวกรองต้องไม่ดีดกลับไปวิชาแรก
  rclick(uItems()[1]);
  rclick(rd('#resetFilterBtn'));
  chk('ล้างตัวกรองไม่เปลี่ยนวิชาที่เลือกไว้', cItems()[1].classList.contains('active'), '');

  // วิชาที่เลือกเป็นความชอบส่วนตัว ต้องอยู่ข้ามการรีเฟรช
  const ui = JSON.parse(r.w.localStorage.getItem('funnymath-ui-v1') || '{}');
  chk('บันทึกวิชาที่เลือกไว้', ui.course === name(second), JSON.stringify(ui.course));
  const back = load({ key: 'funnymath-ui-v1', value: { course: ui.course } });
  chk('รีเฟรชแล้วยังอยู่ที่วิชาเดิม',
      back.d.querySelectorAll('#courseList .fitem')[1].classList.contains('active'), '');
  const bogus = load({ key: 'funnymath-ui-v1', value: { course: 'วิชาที่ไม่มีอยู่จริง' } });
  chk('วิชาที่บันทึกไว้ไม่มีอยู่แล้วกลับไปใช้วิชาแรก',
      bogus.d.querySelectorAll('#courseList .fitem')[0].classList.contains('active'), '');

  // ทุกวิชาต้องเปิดได้และมีข้อสอบ
  for (let i = 0; i < cItems().length; i++) {
    const rr = load();
    const rrclick = el => el.dispatchEvent(new rr.w.Event('click'));
    rrclick(rr.d.querySelectorAll('#courseList .fitem')[i]);
    const n = +(rr.d.querySelector('#navCenter').textContent.match(/\/\s*(\d+)/) || [0, 0])[1];
    const units = rr.d.querySelectorAll('#unitList .fitem').length - 1;
    chk(`วิชาที่ ${i + 1} เปิดได้และมีหน่วยครบ`,
        n > 0 && units > 0 && !!rr.d.querySelector('.qtext'), `${n} ข้อ / ${units} หน่วย`);
  }
}

// ---------- ภาพรวมข้อสอบ: เกือบเต็มจอ · แบ่งตามหน่วย · บอกสถานะรายข้อ ----------
{
  // ป้อนสถานะไว้ล่วงหน้า จะได้ตรวจสีของแต่ละสถานะได้แน่นอน
  //   ข้อ 1 ติ๊กว่าทำแล้วเอง · ข้อ 2 ทำแล้ว+ตอบถูก · ข้อ 3 ตอบผิด · ข้อ 4 ตรวจเองไม่ได้ · ข้อ 5 ยังไม่แตะ
  const key = Object.keys(w.localStorage).find(k => PROGRESS.test(k));
  const r = load({ key, value: {
    done: [0, 1], work: {}, finalAns: {},
    checked: { 1: 'ok', 2: 'no', 3: 'manual' }
  }});
  const rd = s => r.d.querySelector(s);
  const rall = s => [...r.d.querySelectorAll(s)];
  const rclick = el => el.dispatchEvent(new r.w.Event('click'));

  rclick(rd('#overviewBtn'));
  chk('เปิดภาพรวมข้อสอบได้', rd('#overviewOverlay').classList.contains('show'));

  // --- เกือบเต็มจอ ---
  const modal = rd('#overviewOverlay .modal');
  chk('ภาพรวมใช้กล่องแบบเต็มจอ', modal.classList.contains('overview'), modal.className);
  chk('กล่องภาพรวมกว้างเกือบเต็มจอ', /\.modal\.overview\{[^}]*width:96vw/.test(html.replace(/\s/g, '')),
      '');
  chk('กล่องภาพรวมสูงเกือบเต็มจอ', /\.modal\.overview\{[^}]*height:94vh/.test(html.replace(/\s/g, '')),
      '');
  chk('ภาพรวมประกาศเป็น dialog', modal.getAttribute('role') === 'dialog'
      && modal.getAttribute('aria-modal') === 'true', modal.getAttribute('role'));
  chk('หัวเรื่องกับคำอธิบายสัญลักษณ์ตรึงไว้ เลื่อนเฉพาะตาราง',
      !!rd('#overviewOverlay .ov-head') && !!rd('#overviewOverlay .ov-foot')
      && rd('#gridNav').classList.contains('ov-body'), '');

  // --- แบ่งตามหน่วยการเรียนรู้ ---
  const UNITS_IN_COURSE = rall('#unitList .fitem').length - 1;
  const secs = () => rall('#gridNav .ov-unit');
  chk('แบ่งตามหน่วยการเรียนรู้ครบทุกหน่วย', secs().length === UNITS_IN_COURSE,
      `${secs().length} กลุ่ม / ${UNITS_IN_COURSE} หน่วย`);
  chk('ทุกกลุ่มมีเลขหน่วย ชื่อหน่วย และจำนวนที่ทำแล้ว',
      secs().every(s => s.querySelector('.ov-unit-head .u-num')
        && s.querySelector('.ov-unit-head .u-name')
        && /ทำแล้ว/.test(s.querySelector('.ov-unit-head .u-stat').textContent)),
      secs()[0].querySelector('.ov-unit-head').textContent.trim());
  chk('เลขหน่วยของกลุ่มแรกคือหน่วย 1', secs()[0].querySelector('.u-num').textContent === '1',
      secs()[0].querySelector('.u-num').textContent);
  const btns = () => rall('#gridNav .grid-nav button');
  chk('จำนวนปุ่มรวมเท่ากับจำนวนข้อทั้งวิชา', btns().length === TOTAL, `${btns().length} / ${TOTAL}`);
  chk('กลุ่มหน่วย 1 มีข้อครบตามตัวกรอง',
      secs()[0].querySelectorAll('button').length === +rall('#unitList .fitem')[1].querySelector('.cnt').textContent,
      secs()[0].querySelectorAll('button').length);

  // --- สถานะรายข้อ ---
  const b = btns();
  chk('ติ๊กว่าทำแล้วเอง -> สถานะ "ทำแล้ว"', b[0].classList.contains('gdone'), b[0].className);
  chk('ตอบถูก -> สีเขียว', b[1].classList.contains('gok') && !b[1].classList.contains('gdone'),
      b[1].className);
  chk('ตอบผิด -> สีแดง', b[2].classList.contains('gno'), b[2].className);
  chk('ตรวจอัตโนมัติไม่ได้ -> สถานะแยกต่างหาก', b[3].classList.contains('gmanual'), b[3].className);
  chk('ยังไม่ทำ -> ไม่มีสีสถานะ',
      !/gok|gno|gmanual|gdone/.test(b[4].className), b[4].className || '(ว่าง)');
  chk('ข้อปัจจุบันมีกรอบไฮไลต์', b[0].classList.contains('gcur'), b[0].className);
  chk('กรอบข้อปัจจุบันไม่ทับสีสถานะ', b[0].classList.contains('gdone'), b[0].className);
  chk('ทุกปุ่มมี title บอกสถานะ',
      b.every(e => /ยังไม่ทำ|ทำแล้ว|ตอบถูก|ตอบผิด|ตรวจอัตโนมัติไม่ได้/.test(e.title)), b[2].title);

  // --- สรุปด้านบนและคำอธิบายสัญลักษณ์ ---
  const sub = rd('#overviewSub').textContent;
  chk('สรุปนับผลถูก-ผิดได้ถูกต้อง', /ถูก 1/.test(sub) && /ผิด 1/.test(sub), sub);
  chk('สรุปนับข้อที่ยังไม่ทำ', new RegExp(`ยังไม่ทำ ${TOTAL - 4}`).test(sub), sub);
  chk('คำอธิบายสัญลักษณ์ครบทุกสถานะ',
      ['cur', 'ok', 'no', 'manual', 'done'].every(c => !!rd(`#overviewOverlay .legend i.${c}`)), '');

  // --- ตัวกรองหน่วยแล้วเหลือกลุ่มเดียว · กดแล้วไปข้อนั้น ---
  rclick(rd('#closeOverviewBtn'));
  chk('ปิดภาพรวมได้', !rd('#overviewOverlay').classList.contains('show'));
  rclick(rall('#unitList .fitem')[2]);          // เลือกหน่วยที่ 2
  rclick(rd('#overviewBtn'));
  chk('กรองหน่วยเดียวแล้วเหลือกลุ่มเดียว', secs().length === 1, secs().length);
  chk('กลุ่มที่เหลือคือหน่วยที่เลือก', secs()[0].querySelector('.u-num').textContent === '2',
      secs()[0].querySelector('.u-num').textContent);
  const target = btns()[3];
  const want = target.textContent;
  rclick(target);
  chk('กดเลขข้อในภาพรวมแล้วไปข้อนั้น', rd('.qnum-big').textContent.trim() === `ข้อที่ ${want}`,
      `${rd('.qnum-big').textContent.trim()} vs ข้อที่ ${want}`);
  chk('กดเลขข้อแล้วปิดภาพรวมให้เอง', !rd('#overviewOverlay').classList.contains('show'));
}

// ---------- ผลลัพธ์ ----------
const failed = T.filter(t => t[0] === 'FAIL');
console.log(T.map(([s, n, e]) => `${s}  ${n}${s === 'FAIL' ? '   << ' + e : ''}`).join('\n'));
console.log(`\n${T.length - failed.length}/${T.length} ผ่าน`);
if (errs.length) console.log('JS ERRORS:\n' + errs.join('\n'));
process.exit(failed.length || errs.length ? 1 : 0);
