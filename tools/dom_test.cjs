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

// ทุก load() เริ่มที่หน้าแรก — บล็อกที่ทดสอบหน้าข้อสอบต้องกดเข้าไปก่อน
const enterExam = (r, nth = 0) => {
  const b = [...r.d.querySelectorAll('#courseGrid .course-card .c-go')][nth];
  b.dispatchEvent(new r.w.Event('click'));
  return r;
};

const { dom, d, w, errs } = load();
const $ = s => d.querySelector(s);
const $$ = s => [...d.querySelectorAll(s)];
const click = el => el.dispatchEvent(new w.Event('click'));
const type = (el, v) => { el.value = v; el.dispatchEvent(new w.Event('input')); };
const items = id => $$('#' + id + ' .fitem');
const count = el => +el.querySelector('.cnt').textContent;
const label = el => el.querySelector('.fname').textContent;
const shown = () => +($('#navCenter').textContent.match(/\/\s*(\d+)/) || [0, 0])[1];

// ---------- หน้าแรก: เปิดเว็บมาเจอก่อนเสมอ ----------
chk('เปิดเว็บมาอยู่ที่หน้าแรก',
    !$('#homeView').classList.contains('hide') && $('#examView').classList.contains('hide'), '');
chk('หน้าแรกซ่อนปุ่มที่ใช้เฉพาะหน้าข้อสอบ', $('#examActions').classList.contains('hide'), '');
chk('หน้าแรกซ่อนปุ่มหน้าแรกของตัวเอง', $('#homeBtn').classList.contains('hide'), '');
chk('หัวเรื่องหน้าแรกบอกจำนวนข้อทั้งคลัง', /คลังข้อสอบ/.test($('#mainTitle').textContent),
    $('#mainTitle').textContent);
chk('มีการ์ดครบทุกวิชา',
    $$('#courseGrid .course-card').length === $$('#courseList .fitem').length,
    `${$$('#courseGrid .course-card').length} การ์ด`);
chk('การ์ดวิชาบอกจำนวนข้อและจำนวนหน่วย',
    $$('#courseGrid .course-card .c-count').every(e => /ข้อ.*หน่วย/.test(e.textContent)),
    $('#courseGrid .c-count').textContent);
chk('การ์ดวิชาบอกความก้าวหน้า ถูก และผิด',
    !!$('#courseGrid .c-stat .ok') && !!$('#courseGrid .c-stat .no'),
    $('#courseGrid .c-stat').textContent.replace(/\s+/g, ' ').trim());
chk('ยังไม่เคยทำข้อสอบจึงไม่มีปุ่มทำต่อ', !$('#resumeBtn'), '');
chk('แถบบนหัวเรื่องบอกความก้าวหน้ารวมทุกวิชา',
    /ทำแล้ว 0 \//.test($('#progressLabel').textContent), $('#progressLabel').textContent);

// ปุ่มบนการ์ดวิชาแรกพาเข้าหน้าข้อสอบ
const firstCourseName = $('#courseGrid .c-name').textContent;
click($('#courseGrid .course-card .c-go'));
chk('กดเริ่มทำข้อสอบแล้วเข้าหน้าข้อสอบ',
    $('#homeView').classList.contains('hide') && !$('#examView').classList.contains('hide'), '');
chk('เข้าหน้าข้อสอบแล้วปุ่มหน้าแรกโผล่', !$('#homeBtn').classList.contains('hide'), '');
chk('เข้าตรงวิชาที่กด', $('#mainTitle').textContent.includes(firstCourseName),
    $('#mainTitle').textContent);

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
  const r = enterExam(load({ key, value: { done: [0, 5], work: { 0: ['a', 'b', 'c'] }, finalAns: { 0: '42' }, checked: {} } }));
  const rd = s => r.d.querySelector(s);
  chk('รีเฟรชแล้วกู้วิธีทำกลับมา', r.d.querySelectorAll('#workLines .work-line').length === 3,
      r.d.querySelectorAll('#workLines .work-line').length);
  chk('รีเฟรชแล้วกู้คำตอบกลับมา', rd('#finalInput').value === '42', rd('#finalInput').value);
  chk('รีเฟรชแล้วกู้จำนวนข้อที่ทำแล้ว', rd('#progressLabel').textContent.includes('ทำแล้ว 2'),
      rd('#progressLabel').textContent);
  chk('ข้อมูลที่บันทึกเสียหายก็ยังเปิดหน้าได้',
      !!enterExam(load({ key, value: 'ไม่ใช่ JSON' })).d.querySelector('#finalInput'));

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
  const r = enterExam(load());
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
      enterExam(load({ key: 'funnymath-ui-v1', value: { sidebarOpen: true } }))
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
  const r = enterExam(load());
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
    const rr = enterExam(load());
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
  const r = enterExam(load({ key, value: {
    done: [0, 1], work: {}, finalAns: {},
    checked: { 1: 'ok', 2: 'no', 3: 'manual' }
  }}));
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

// ---------- หน้าแรก: ทางลัดไปหน่วย · ปุ่มทำต่อ · กลับหน้าแรก ----------
{
  const r = load();
  const rd = s => r.d.querySelector(s);
  const rall = s => [...r.d.querySelectorAll(s)];
  const rclick = el => el.dispatchEvent(new r.w.Event('click'));

  // ทางลัดของแต่ละวิชาต้องมีครบทุกหน่วย
  const cards = rall('#courseGrid .course-card');
  const chipCounts = cards.map(c => c.querySelectorAll('.c-units button').length);
  chk('ทุกการ์ดมีทางลัดไปหน่วยครบ', chipCounts.every(n => n > 0), chipCounts.join('/'));
  chk('ทางลัดหน่วยบอกทั้งเลขหน่วยและชื่อหน่วย',
      !!rd('#courseGrid .c-units button .u-n') && !!rd('#courseGrid .c-units button .u-t'),
      rd('#courseGrid .c-units button').textContent);

  // กดทางลัดหน่วยที่ 3 ของวิชาที่สอง -> เข้าหน้าข้อสอบพร้อมตัวกรองหน่วยนั้น
  const card2 = cards[1];
  const wantCourse = card2.querySelector('.c-name').textContent;
  const chip = card2.querySelectorAll('.c-units button')[2];
  const wantUnit = chip.querySelector('.u-n').textContent;
  rclick(chip);
  chk('กดทางลัดหน่วยแล้วเข้าหน้าข้อสอบ', !rd('#examView').classList.contains('hide'), '');
  chk('ทางลัดหน่วยพาไปวิชาที่ถูกต้อง', rd('#mainTitle').textContent.includes(wantCourse),
      rd('#mainTitle').textContent);
  chk('ทางลัดหน่วยตั้งตัวกรองหน่วยให้เลย',
      rd('#group-unit .fhead .fsel').textContent === `หน่วย ${wantUnit}`,
      rd('#group-unit .fhead .fsel').textContent);
  chk('ทางลัดหน่วยไม่ติดตัวกรองอื่นมาด้วย', rd('#filterBadge').textContent === '1',
      rd('#filterBadge').textContent);

  // กลับหน้าแรกแล้วตัวเลขต้องอัปเดตตามที่เพิ่งทำไป
  // ช่องติ๊กต้องตั้งค่าแล้วยิง change เอง — Event('click') เปล่า ๆ ไม่ toggle ให้
  const dc = rd('#doneCheck');
  dc.checked = true;
  dc.dispatchEvent(new r.w.Event('change'));
  rclick(rd('#homeBtn'));
  chk('กดหน้าแรกแล้วกลับมาหน้าแรกได้',
      !rd('#homeView').classList.contains('hide') && rd('#examView').classList.contains('hide'), '');
  chk('กลับหน้าแรกแล้วตัวเลขความก้าวหน้าอัปเดต',
      /ทำแล้ว 1 \//.test(rd('#progressLabel').textContent), rd('#progressLabel').textContent);
  chk('การ์ดของวิชาที่เพิ่งทำนับเพิ่มให้',
      /ทำแล้ว\s*1\s*\//.test(rall('#courseGrid .course-card')[1].querySelector('.c-stat').textContent),
      rall('#courseGrid .course-card')[1].querySelector('.c-stat').textContent.replace(/\s+/g, ' '));

  // เปิดข้อสอบแล้วต้องได้ปุ่ม "ทำต่อ" ที่พากลับไปข้อเดิม
  chk('เคยเปิดข้อสอบแล้วจึงมีปุ่มทำต่อ', !!rd('#resumeBtn'), '');
  const resumeLine = rd('.resume .r-main').textContent;
  rclick(rd('#resumeBtn'));
  chk('ปุ่มทำต่อพากลับเข้าหน้าข้อสอบ', !rd('#examView').classList.contains('hide'), '');
  chk('ปุ่มทำต่อกลับไปข้อเดิม',
      resumeLine.includes(rd('.qnum-big').textContent.trim().replace('ข้อที่ ', 'ข้อที่ ')),
      `${resumeLine} vs ${rd('.qnum-big').textContent.trim()}`);

  // ข้อล่าสุดต้องอยู่ข้ามการรีเฟรช
  const ui = JSON.parse(r.w.localStorage.getItem('funnymath-ui-v1') || '{}');
  chk('บันทึกข้อล่าสุดไว้', Number.isInteger(ui.lastGidx), JSON.stringify(ui.lastGidx));
  const back = load({ key: 'funnymath-ui-v1', value: { lastGidx: 5 } });
  chk('รีเฟรชแล้วยังมีปุ่มทำต่อ', !!back.d.querySelector('#resumeBtn'), '');
  chk('ปุ่มทำต่อชี้ไปข้อที่บันทึกไว้',
      /ข้อที่ 6/.test(back.d.querySelector('.resume .r-main').textContent),
      back.d.querySelector('.resume .r-main').textContent);
  const bad = load({ key: 'funnymath-ui-v1', value: { lastGidx: 999999 } });
  chk('ข้อล่าสุดที่ไม่มีอยู่จริงไม่ทำให้หน้าแรกพัง',
      !bad.d.querySelector('#resumeBtn') && !!bad.d.querySelector('#courseGrid .course-card'), '');
}

// ---------- ติวเตอร์ AI ----------
// ยัด fetch ปลอมที่คืนสตรีม SSE ให้ ไม่ต้องต่อเน็ตจริงและไม่ต้องมีคีย์จริง
function loadTutor(seeds, reply = 'ลองอ่านโจทย์อีกครั้ง โจทย์ให้อะไรมาบ้าง?') {
  const sent = [];
  const sse = [
    { type: 'message_start', message: { id: 'msg_1' } },
    { type: 'content_block_start', index: 0, content_block: { type: 'text', text: '' } },
    { type: 'content_block_delta', index: 0, delta: { type: 'text_delta', text: reply } },
    { type: 'content_block_stop', index: 0 },
    { type: 'message_delta', delta: { stop_reason: 'end_turn' } },
    { type: 'message_stop' },
  ].map(e => `event: ${e.type}\ndata: ${JSON.stringify(e)}\n\n`).join('');

  const dom = new JSDOM(html, {
    runScripts: 'dangerously',
    pretendToBeVisual: true,
    url: 'https://tkosin.github.io/math-is-fun/',
    beforeParse(w) {
      seeds.forEach(s => w.localStorage.setItem(s.key, JSON.stringify(s.value)));
      w.fetch = (url, opt) => {
        sent.push({ url, headers: opt.headers, body: JSON.parse(opt.body) });
        const bytes = new w.TextEncoder().encode(sse);
        let done = false;
        return Promise.resolve({
          ok: true, status: 200,
          body: { getReader: () => ({
            read: () => Promise.resolve(done ? { done: true } : (done = true, { value: bytes, done: false })),
          }) },
        });
      };
    },
  });
  dom.virtualConsole.on('jsdomError', e => errs.push(e.message));
  const r = { dom, d: dom.window.document, w: dom.window, sent };
  const go = [...r.d.querySelectorAll('#courseGrid .course-card .c-go')][0];
  go.dispatchEvent(new r.w.Event('click'));
  return r;
}
const tclick = (r, sel) => r.d.querySelector(sel).dispatchEvent(new r.w.Event('click'));
const tick = () => new Promise(res => setTimeout(res, 0));
// รอจนเงื่อนไขเป็นจริง (สตรีมคำตอบใช้หลาย microtask จึงรอด้วย setTimeout)
const waitFor = async (fn, n = 80) => { for (let i = 0; i < n && !fn(); i++) await tick(); return fn(); };

{
  const KEY = { key: 'funnymath-ai-v1', value: { key: 'sk-ant-test', model: 'claude-opus-5' } };

  // ยังไม่ใส่คีย์ → ต้องชวนไปตั้งค่า ไม่ใช่ช่องพิมพ์
  const noKey = loadTutor([{ key: 'funnymath-ui-v1', value: { tutorOpen: true } }]);
  chk('ยังไม่ใส่คีย์ → แผงติวเตอร์ชวนไปตั้งค่า',
      !!noKey.d.querySelector('#tutorSetupBtn') && !noKey.d.querySelector('#tutorInput'), '');
  tclick(noKey, '#tutorSetupBtn');
  chk('กดตั้งค่าแล้วเปิดหน้าต่างใส่คีย์', noKey.d.querySelector('#aiOverlay').classList.contains('show'), '');

  // แผงด้านขวา: กาง/พับ, ปุ่มปิดในแผง, Esc, และการจำสถานะ
  const t = loadTutor([KEY]);
  const panel = t.d.querySelector('#tutorPanel');
  chk('แผงติวเตอร์อยู่นอกการ์ดข้อสอบ', !!panel && !t.d.querySelector('#examCard #tutorPanel'), '');
  chk('แผงติวเตอร์พับไว้ตั้งแต่เริ่ม',
      !panel.classList.contains('show') && panel.getAttribute('aria-hidden') === 'true', '');
  chk('ยังไม่กางแผง → เนื้อหาไม่ถูกเบียด', !t.d.body.classList.contains('tutor-on'), '');
  tclick(t, '#tutorToggle');
  chk('กดปุ่มแล้วกางแผงด้านขวา',
      panel.classList.contains('show') && panel.getAttribute('aria-hidden') === 'false', '');
  chk('กางแผงแล้วเบียดเนื้อหาไปทางซ้าย', t.d.body.classList.contains('tutor-on'), '');
  // เบียดแล้วต้องขยายเพดานความกว้างขึ้นเท่าความกว้างแผง ไม่ใช่บีบพื้นที่ข้อสอบให้แคบลง
  chk('กางแผงแล้วขยายเพดานความกว้างของเนื้อหาชดเชยให้',
      /max-width:\s*calc\(var\(--maxw\)\s*\+\s*var\(--tutorw\)/.test(html)
      && /body\.tutor-on \.layout\{/.test(html.replace(/\s*\n\s*/g, '')), '');
  chk('กางแล้วมีช่องพิมพ์ถามอยู่ในแผง', !!t.d.querySelector('#tutorPanel #tutorInput'), '');
  chk('หัวแผงบอกว่ากำลังติวข้อไหน', /ข้อที่ \d+/.test(t.d.querySelector('#tutorWhich').textContent),
      t.d.querySelector('#tutorWhich').textContent);
  chk('ปุ่มกางบอกสถานะด้วย aria-expanded',
      t.d.querySelector('#tutorToggle').getAttribute('aria-expanded') === 'true', '');
  chk('จำสถานะกางไว้ใน localStorage',
      JSON.parse(t.w.localStorage.getItem('funnymath-ui-v1') || '{}').tutorOpen === true, '');
  tclick(t, '#tutorClose');
  chk('ปุ่ม ✕ ในแผงปิดแผงได้',
      !panel.classList.contains('show') && !t.d.body.classList.contains('tutor-on'), '');
  chk('ปิดแผงแล้วปุ่มในการ์ดกลับเป็น "ถามพี่หลวง"',
      /ถามพี่หลวง/.test(t.d.querySelector('#tutorToggle').textContent),
      t.d.querySelector('#tutorToggle').textContent);
  tclick(t, '#tutorToggle');
  t.d.dispatchEvent(new t.w.KeyboardEvent('keydown', { key: 'Escape' }));
  chk('Esc ปิดแผงติวเตอร์', !panel.classList.contains('show'), '');

  const opened = [{ key: 'funnymath-ui-v1', value: { tutorOpen: true } }, KEY];
  const t2 = loadTutor(opened);
  chk('เคยกางไว้ → เข้าข้อสอบก็กางให้เลย', !!t2.d.querySelector('#tutorInput'), '');
  // หน้าแรกไม่มีข้อให้ติว แผงต้องไม่ค้างอยู่
  const homeOpen = loadTutor(opened);
  homeOpen.d.querySelector('#homeBtn').dispatchEvent(new homeOpen.w.Event('click'));
  chk('กลับหน้าแรกแล้วซ่อนแผงติวเตอร์',
      !homeOpen.d.querySelector('#tutorPanel').classList.contains('show')
      && !homeOpen.d.body.classList.contains('tutor-on'), '');
  chk('กลับหน้าแรกแล้วยังจำสถานะกางไว้',
      JSON.parse(homeOpen.w.localStorage.getItem('funnymath-ui-v1') || '{}').tutorOpen === true, '');
  chk('เริ่มต้นอยู่คำใบ้ขั้นที่ 1',
      /ขั้นที่ 1 \/ 7/.test(t2.d.querySelector('.tutor-rung').textContent),
      t2.d.querySelector('.tutor-rung').textContent);

  (async () => {
    // ถาม 1 ครั้ง → ต้องยิง request ที่มีเฮดเดอร์ครบและได้คำตอบขึ้นจอ
    const input = t2.d.querySelector('#tutorInput');
    input.value = 'ไม่รู้จะเริ่มยังไง';
    input.dispatchEvent(new t2.w.Event('input'));
    tclick(t2, '#tutorSend');
    await waitFor(() => (t2.d.querySelector('.bubble.ai') || {}).textContent);

    const req = t2.sent[0] || { headers: {}, body: {} };
    chk('ถามแล้วยิงไปที่ Messages API', /api\.anthropic\.com\/v1\/messages$/.test(t2.sent[0] && t2.sent[0].url),
        t2.sent[0] && t2.sent[0].url);
    chk('ส่งเฮดเดอร์เรียกจากเบราว์เซอร์ตรง',
        req.headers['anthropic-dangerous-direct-browser-access'] === 'true', '');
    chk('ส่ง x-api-key และเวอร์ชัน API',
        req.headers['x-api-key'] === 'sk-ant-test' && !!req.headers['anthropic-version'], '');
    chk('เรียกแบบสตรีม', req.body.stream === true, '');
    chk('พรอมป์ระบบมีทั้งโจทย์ เฉลย และขั้นของคำใบ้',
        /## โจทย์ที่กำลังทำ/.test(req.body.system) && /## เฉลย/.test(req.body.system)
        && /ขั้นที่ 1 จาก 7/.test(req.body.system), '');
    chk('พรอมป์ระบบสั่งห้ามบอกคำตอบในขั้นต้น',
        /ห้ามบอกคำตอบสุดท้ายเด็ดขาดในขั้นนี้/.test(req.body.system), '');
    chk('พรอมป์ระบบตั้งบุคลิกเป็นพี่หลวง รุ่นพี่ผู้ชาย',
        /คุณคือ "พี่หลวง"/.test(req.body.system) && /รุ่นพี่ผู้ชาย/.test(req.body.system), '');
    chk('พรอมป์ระบบสั่งลงท้าย "ครับ" และห้าม "จ๊ะ"',
        /"ครับ" หรือ "ครับน้อง"/.test(req.body.system) && /ห้ามใช้คำลงท้ายแบบผู้หญิง/.test(req.body.system)
        && /"จ๊ะ"/.test(req.body.system), '');
    chk('พรอมป์ระบบบอกสัญกรณ์คณิตศาสตร์ที่หน้าเว็บจัดรูปได้ และห้าม LaTeX',
        /ยกกำลังใช้ \^/.test(req.body.system) && /ห้ามใช้ LaTeX ทุกชนิด/.test(req.body.system), '');
    chk('แผงและปุ่มเรียกชื่อพี่หลวงตรงกัน',
        /พี่หลวง/.test(t2.d.querySelector('.tp-title').textContent)
        && /พี่หลวง/.test(t2.d.querySelector('#tutorToggle').textContent), '');
    chk('พรอมป์ระบบไม่มีแท็ก HTML ของโจทย์ติดไปด้วย',
        !/<(div|span|svg|sup)\b/.test(req.body.system), '');
    chk('คำตอบติวเตอร์ขึ้นในกล่องแช็ต',
        /ลองอ่านโจทย์อีกครั้ง/.test((t2.d.querySelector('.bubble.ai') || {}).textContent || ''), '');
    chk('ถามแล้วขั้นคำใบ้ขยับเป็น 2',
        /ขั้นที่ 2 \/ 7/.test(t2.d.querySelector('.tutor-rung').textContent),
        t2.d.querySelector('.tutor-rung').textContent);

    const saved = JSON.parse(t2.w.localStorage.getItem('funnymath-chat-v1') || '{}');
    const first = saved[Object.keys(saved)[0]] || [];
    chk('บทสนทนาเก็บลง localStorage แยกตามข้อ',
        first.length === 2 && first[0].r === 'u' && first[1].r === 'a', JSON.stringify(first.length));

    // คำตอบของติวเตอร์ต้องออกมาเป็นสมการจริง ไม่ใช่ข้อความ ^ กับ /
    const math = loadTutor(opened,
      'พื้นที่ = a^2 ครับ · 10^(-2) · a_1 · 3/4 · x >= 2 · 3*4 · $\\frac{1}{2}$ · \\sqrt{16}');
    const mi = math.d.querySelector('#tutorInput');
    mi.value = 'ขอสมการ';
    tclick(math, '#tutorSend');
    await waitFor(() => (math.d.querySelector('.bubble.ai') || {}).textContent);
    const mathHtml = math.d.querySelector('.bubble.ai').innerHTML;
    chk('ยกกำลังเรนเดอร์เป็น <sup> จริง', /a<sup>2<\/sup>/.test(mathHtml), mathHtml.slice(0, 60));
    chk('ยกกำลังในวงเล็บก็เป็น <sup>', /10<sup>-2<\/sup>/.test(mathHtml), '');
    chk('ตัวห้อยเรนเดอร์เป็น <sub>', /a<sub>1<\/sub>/.test(mathHtml), '');
    chk('เศษส่วนเรนเดอร์เป็นชั้นบน/ล่าง (.frac)',
        /<span class="frac"><span class="num">3<\/span><span class="den">4<\/span><\/span>/.test(mathHtml), '');
    chk('เครื่องหมายเปรียบเทียบเป็นสัญลักษณ์', /x ≥ 2/.test(mathHtml), '');
    chk('เครื่องหมายคูณเป็น ×', /3 × 4/.test(mathHtml), '');
    chk('โมเดลหลุดไปเขียน LaTeX ก็ยังจัดรูปให้ได้',
        /<span class="num">1<\/span>/.test(mathHtml) && /√\(16\)/.test(mathHtml) && !/frac\{/.test(mathHtml), '');
    // ต้อง "ไม่" จับ / ที่ไม่ใช่เศษส่วน ไม่งั้นตัวชี้วัดกับคำว่า และ/หรือ จะเพี้ยน
    const slash = loadTutor(opened, 'ตัวชี้วัด ค 2.1 ม.2/1 และ/หรือ เรื่องปริซึม');
    slash.d.querySelector('#tutorInput').value = 'ถาม';
    tclick(slash, '#tutorSend');
    await waitFor(() => (slash.d.querySelector('.bubble.ai') || {}).textContent);
    const plain = slash.d.querySelector('.bubble.ai').innerHTML;
    chk('ไม่จับ / ที่ไม่ใช่เศษส่วน (ตัวชี้วัด · และ/หรือ)',
        !/class="frac"/.test(plain) && /ม\.2\/1 และ\/หรือ/.test(plain), plain.slice(0, 60));

    // เพดานคำใบ้ต้องผูกกับรหัสผ่านเฉลย
    const chat = { 0: Array.from({ length: 12 }, (_, i) => ({ r: i % 2 ? 'a' : 'u', t: 'x' })) };
    const many = loadTutor([...opened, { key: 'funnymath-chat-v1', value: chat }]);
    chk('ยังไม่ปลดล็อกเฉลย → คำใบ้หยุดที่ขั้น 6',
        /ขั้นที่ 6 \/ 7/.test(many.d.querySelector('.tutor-rung').textContent),
        many.d.querySelector('.tutor-rung').textContent);
    chk('บอกวิธีปลดล็อกให้ถึงขั้นเฉลยเต็ม',
        /ดูเฉลย/.test(many.d.querySelector('.tutor-hint').textContent), '');
    tclick(many, '#revealBtn');
    const pw = many.d.querySelector('#pwInput');
    pw.value = /const ANSWER_PASSWORD = "(.*?)"/.exec(html)[1];
    tclick(many, '#pwConfirmBtn');
    chk('ปลดล็อกเฉลยแล้วคำใบ้ขึ้นถึงขั้น 7',
        /ขั้นที่ 7 \/ 7/.test(many.d.querySelector('.tutor-rung').textContent),
        many.d.querySelector('.tutor-rung').textContent);

    // เริ่มบทสนทนาใหม่แล้วต้องนับขั้นใหม่
    tclick(many, '#tutorReset');
    chk('เริ่มบทสนทนาใหม่แล้วกลับไปขั้นที่ 1',
        /ขั้นที่ 1 \/ 7/.test(many.d.querySelector('.tutor-rung').textContent)
        && !many.d.querySelector('.bubble'), '');

    // Haiku ไม่รับ output_config.effort
    const haiku = loadTutor([...opened, { key: 'funnymath-ai-v1', value: { key: 'k', model: 'claude-haiku-4-5' } }]);
    const hi = haiku.d.querySelector('#tutorInput');
    hi.value = 'ถาม';
    tclick(haiku, '#tutorSend');
    await waitFor(() => haiku.sent.length);
    chk('เลือก Haiku 4.5 → ไม่ส่ง output_config ไปด้วย',
        haiku.sent.length === 1 && !('output_config' in haiku.sent[0].body)
        && haiku.sent[0].body.model === 'claude-haiku-4-5', JSON.stringify(Object.keys(haiku.sent[0].body)));

    report();
  })().catch(e => {
    chk('ชุดเทสต์ติวเตอร์ AI ทำงานจบ', false, e && e.message);
    report();
  });
}

// ---------- ผลลัพธ์ ----------
// เทสต์ของติวเตอร์ AI เป็น async (รอสตรีมคำตอบ) จึงสรุปผลเมื่อชุดนั้นจบ
function report() {
  const failed = T.filter(t => t[0] === 'FAIL');
  console.log(T.map(([s, n, e]) => `${s}  ${n}${s === 'FAIL' ? '   << ' + e : ''}`).join('\n'));
  console.log(`\n${T.length - failed.length}/${T.length} ผ่าน`);
  if (errs.length) console.log('JS ERRORS:\n' + errs.join('\n'));
  process.exit(failed.length || errs.length ? 1 : 0);
}
