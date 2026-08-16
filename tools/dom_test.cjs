/**
 * ทดสอบพฤติกรรมหน้าเว็บด้วย jsdom — ตัวกรอง, ช่องวิธีทำ, การตรวจคำตอบ, การบันทึก
 *
 * รัน:  npm i jsdom --no-save && node tools/dom_test.cjs
 * จำนวนข้อสอบอ่านจากข้อมูลจริง จึงไม่ต้องแก้เทสต์ทุกครั้งที่เพิ่มข้อสอบ
 */
const fs = require('fs');
const path = require('path');
const { JSDOM } = require('jsdom');

// index.html เสิร์ฟออนไลน์และโหลด data/*.json ทีหลัง ส่วนสำเนาชื่อไทยรวมทุกอย่างไว้ในไฟล์เดียว
// jsdom ไม่มีเซิร์ฟเวอร์ให้ fetch เทสต์ส่วนใหญ่จึงรันบนสำเนา (โค้ดชุดเดียวกันเป๊ะ)
// ส่วนเส้นทาง "โหลดรายวิชา" มีบล็อกทดสอบแยกที่ stub fetch ให้
const SHELL_HTML = path.join(__dirname, '..', 'index.html');
const HTML = path.join(__dirname, '..', 'คลังข้อสอบ_ออฟไลน์.html');
const html = fs.readFileSync(HTML, 'utf8');
const shellHtml = fs.readFileSync(SHELL_HTML, 'utf8');
const DATA_DIR = path.join(__dirname, '..', 'data');

const T = [];
let LAZY = Promise.resolve();   // ชุดเทสต์ที่ต้องรอ fetch
const chk = (name, cond, extra = '') => T.push([cond ? 'PASS' : 'FAIL', name, String(extra)]);

function load(seed) {
  const errs = [];
  const dom = new JSDOM(html, {
    runScripts: 'dangerously',
    pretendToBeVisual: true,
    url: 'https://tkosin.github.io/Thai-Exam-AI-Socratic-Tutor/',
    beforeParse(w) {
      if (seed) w.localStorage.setItem(seed.key, JSON.stringify(seed.value));
    },
  });
  dom.virtualConsole.on('jsdomError', e => errs.push(e.message));
  return { dom, d: dom.window.document, w: dom.window, errs };
}

// ทุก load() เริ่มที่หน้าแรก — บล็อกที่ทดสอบหน้าข้อสอบต้องกดเข้าไปก่อน
// เลือกวิชาด้วย "ชื่อวิชา" ไม่ใช่ลำดับการ์ด — ลำดับบนหน้าแรกเปลี่ยนได้เมื่อเพิ่มชั้นใหม่
// (ตอนเพิ่ม ป.5 เข้ามา การ์ดใบแรกกลายเป็น ป.5 แล้วเทสต์ที่ผูกกับ ม.1 ล้มยกชุด)
const enterExam = (r, which = 'คณิตศาสตร์ ม.1') => {
  const cards = [...r.d.querySelectorAll('#courseGrid .course-card')];
  const pick = typeof which === 'number' ? cards[which]
    : cards.find(c => c.textContent.includes(which));
  if (!pick) throw new Error('ไม่พบการ์ดวิชา ' + which);
  pick.querySelector('.c-go').dispatchEvent(new r.w.Event('click'));
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

// ---------- แท็บระดับชั้นบนหน้าแรก ----------
{
  const tabs = () => $$('#homeTabs button');
  const cardNames = () => $$('#courseGrid .c-name').map(e => e.textContent);
  const grades = [...new Set(cardNames().map(n => n.split(' ').pop()))];
  chk('หน้าแรกมีแท็บภาพรวมและแท็บรายชั้นครบ', tabs().length === grades.length + 1,
      tabs().map(b => b.textContent).join(' / '));
  chk('แท็บภาพรวมถูกเลือกไว้ตั้งแต่เปิดหน้า',
      tabs()[0].getAttribute('aria-selected') === 'true',
      tabs()[0].getAttribute('aria-selected'));
  chk('แท็บทุกอันบอกจำนวนข้อของชั้นนั้น',
      tabs().every(b => /[\d,]+ ข้อ/.test(b.textContent)), tabs()[1].textContent);
  // ยอดของแต่ละแท็บรวมกันต้องเท่ากับแท็บภาพรวมพอดี ไม่งั้นมีวิชาตกหล่นหรือถูกนับซ้ำ
  // อ่านจากช่องตัวเลขของแท็บโดยตรง — ชื่อชั้นกับตัวเลขติดกันในข้อความรวม ("ป.5368 ข้อ")
  const nOf = b => +b.querySelector('.t-c').textContent.match(/([\d,]+)/)[1].replace(/,/g, '');
  chk('ยอดของแท็บรายชั้นรวมกันเท่ากับแท็บภาพรวม',
      tabs().slice(1).reduce((a, b) => a + nOf(b), 0) === nOf(tabs()[0]),
      `${tabs().slice(1).reduce((a, b) => a + nOf(b), 0)} vs ${nOf(tabs()[0])}`);

  const allCards = cardNames().length;
  click(tabs()[1]);
  const g = grades[0];
  chk('กดแท็บชั้นแล้วเหลือเฉพาะการ์ดของชั้นนั้น',
      cardNames().length > 0 && cardNames().every(n => n.endsWith(' ' + g)),
      cardNames().join(' / '));
  chk('กดแท็บชั้นแล้วแท็บนั้นถูกเลือก',
      tabs()[1].getAttribute('aria-selected') === 'true', '');
  chk('กดแท็บชั้นแล้วหัวข้อสรุปเปลี่ยนตามชั้น',
      $('#homeSumTitle').textContent.includes(g), $('#homeSumTitle').textContent);
  chk('กดแท็บชั้นแล้วยอดสรุปเป็นของชั้นนั้น ไม่ใช่ทั้งคลัง',
      $('#homeSumNote').textContent.includes(nOf(tabs()[1]).toLocaleString('en-US')),
      $('#homeSumNote').textContent.replace(/\s+/g, ' ').trim());
  click(tabs()[0]);
  chk('กดกลับแท็บภาพรวมแล้วการ์ดครบเหมือนเดิม', cardNames().length === allCards,
      `${cardNames().length} / ${allCards}`);
  chk('กลับแท็บภาพรวมแล้วหัวข้อสรุปกลับเป็นทั้งหมด',
      $('#homeSumTitle').textContent === 'ความก้าวหน้าทั้งหมด', $('#homeSumTitle').textContent);
}
chk('แถบบนหัวเรื่องบอกความก้าวหน้ารวมทุกวิชา',
    /ทำแล้ว 0 \//.test($('#progressLabel').textContent), $('#progressLabel').textContent);

// ปุ่มบนการ์ดวิชาพาเข้าหน้าข้อสอบ
// เลือก ม.1 ด้วยชื่อ ไม่ใช่การ์ดใบแรก — บล็อกที่เหลือของไฟล์นี้ผูกกับหน่วยและป้ายของ ม.1
const m1Card = $$('#courseGrid .course-card')
  .find(c => c.textContent.includes('คณิตศาสตร์ ม.1'));
const firstCourseName = m1Card.querySelector('.c-name').textContent;
click(m1Card.querySelector('.c-go'));
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
// เลือกไว้ตั้งแต่เปิดหน้า = วิชาที่กดเข้ามา ไม่ใช่วิชาที่อยู่บนสุดของรายการ
const activeCourse = () => courses().filter(e => e.classList.contains('active'));
chk('เลือกวิชาที่กดเข้ามาไว้ให้ตั้งแต่เปิดหน้า',
    activeCourse().length === 1 && label(activeCourse()[0]) === firstCourseName,
    courses().map(label).join(' / '));
chk('ตัวกรองวิชาไม่มีตัวเลือก "ทุกวิชา"',
    courses().every(e => !/ทุกวิชา/.test(label(e))), courses().map(label).join(' / '));
chk('จำนวนของทุกวิชารวมกันมากกว่าวิชาเดียว',
    courses().reduce((a, e) => a + count(e), 0) > TOTAL,
    courses().map(e => `${label(e)}:${count(e)}`).join(' · '));
chk('ชื่อเรื่องตรงกับวิชาที่เลือก',
    $('#mainTitle').textContent.includes(label(activeCourse()[0])),
    $('#mainTitle').textContent);
chk('หัวกลุ่มวิชาแสดงวิชาที่เลือกอยู่เสมอ',
    !!d.querySelector('#group-course .fhead .fsel'),
    d.querySelector('#group-course .fhead').textContent.trim());

// ---------- ตัวกรอง 4 ชั้นภายในวิชา ----------
const UNITS = items('unitList').length - 1;      // ไม่นับปุ่ม "ทุกหน่วย"
chk('มีตัวกรองหน่วยครบ (อ่านจากข้อมูล)', UNITS >= 9, UNITS + ' หน่วย');
chk('ทุกปุ่มหน่วยมีเลขหน่วยกำกับ',
    items('unitList').slice(1).every(e => e.querySelector('.unum')), '');
// ---- การเข้าถึงของกล่องซ้อน (a11y) ----
{
  const cr = d.getElementById('checkResult');
  chk('ผลการตรวจคำตอบประกาศให้ screen reader ได้ยิน',
      cr.getAttribute('aria-live') === 'polite' && cr.getAttribute('role') === 'status',
      cr.getAttribute('aria-live') + '/' + cr.getAttribute('role'));

  const key = (k, shift) => d.dispatchEvent(
    new w.KeyboardEvent('keydown', { key: k, shiftKey: !!shift, bubbles: true }));
  const ov = d.getElementById('overviewOverlay');
  const pw = d.getElementById('pwOverlay');
  const ovBtn = d.getElementById('overviewBtn');

  ovBtn.focus();
  ovBtn.click();
  chk('กดปุ่มภาพรวมแล้วกล่องเปิด', ov.classList.contains('show'), ov.className);

  // Tab ต้องวนอยู่ในกล่อง ไม่หลุดออกไปข้างนอก — ต้องทดสอบทั้งสองทิศ
  const inModal = [...ov.querySelectorAll('button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])')]
    .filter(el => !el.disabled && !el.hidden);
  const first = inModal[0], last = inModal[inModal.length - 1];
  last.focus();
  key('Tab');
  chk('Tab ที่ตัวสุดท้ายของกล่องวนกลับมาตัวแรก',
      d.activeElement === first, d.activeElement && d.activeElement.id);
  first.focus();
  key('Tab', true);
  chk('Shift+Tab ที่ตัวแรกของกล่องวนไปตัวสุดท้าย',
      d.activeElement === last, d.activeElement && d.activeElement.id);

  // ปิดกล่องแล้วโฟกัสต้องกลับไปที่ปุ่มที่เปิดมัน
  // ต้องย้ายโฟกัสเข้าไปในกล่องก่อน ไม่งั้นโฟกัสไม่เคยขยับ เทสต์จะผ่านแม้ถอดโค้ดคืนโฟกัสออก
  first.focus();
  key('Escape');
  chk('Esc ปิดกล่องภาพรวมได้', !ov.classList.contains('show'), ov.className);
  chk('ปิดกล่องแล้วคืนโฟกัสให้ปุ่มที่เปิด',
      d.activeElement === ovBtn, d.activeElement && (d.activeElement.id || d.activeElement.tagName));

  // ปุ่ม "ดูเฉลย" อยู่ในการ์ดข้อสอบ หาแบบเดียวกับที่ผู้เรียนเห็น
  const revealBtn = [...d.querySelectorAll('button')].find(b => /ดูเฉลย/.test(b.textContent));
  revealBtn.focus();
  revealBtn.click();
  chk('กดดูเฉลยแล้วกล่องรหัสผ่านเปิด', pw.classList.contains('show'), pw.className);
  d.getElementById('pwInput').focus();
  key('Escape');
  chk('Esc ปิดกล่องรหัสผ่านได้', !pw.classList.contains('show'), pw.className);
  chk('ปิดกล่องรหัสผ่านแล้วคืนโฟกัสให้ปุ่มดูเฉลย',
      d.activeElement === revealBtn, d.activeElement && (d.activeElement.id || d.activeElement.tagName));
}

chk('มีตัวกรองระดับความยาก ครบ 5 ระดับรวมแข่งขันและโอลิมปิก',
    items('levelList').map(label).join('/') === 'ทุกระดับ/ง่าย/กลาง/ยาก/แข่งขัน/โอลิมปิก',
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
// ทุกระดับ + ง่าย/กลาง/ยาก/แข่งขัน/โอลิมปิก = 6 รายการ
chk('กางแล้วเห็นรายการครบ', items('levelList').length === 6, items('levelList').length);
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
// ความก้าวหน้าอ้างด้วยรหัสประจำข้อ ไม่ใช่ลำดับ — เทสต์จึงต้องป้อนด้วย id เหมือนของจริง
// QUESTIONS เป็น const ระดับสคริปต์ ไม่ได้อยู่บน window จึงอ่านจากตัวไฟล์แทน
const ALL_Q = JSON.parse(/const QUESTIONS = (\[[\s\S]*?\]);/.exec(html)[1]);
const QID = i => ALL_Q[i].id;
const keys = Object.keys(w.localStorage);
chk('บันทึกด้วยคีย์ที่มีเลขเวอร์ชัน', keys.some(k => PROGRESS.test(k)), keys.join());
chk('ความชอบส่วนตัวเก็บแยกคีย์', keys.some(k => k === 'funnymath-ui-v1'), keys.join());
const saved = JSON.parse(w.localStorage.getItem(keys.find(k => PROGRESS.test(k))) || '{}');
chk('บันทึกข้อที่ทำแล้วและคำตอบ',
    Array.isArray(saved.done) && saved.done.length === 1 && !!saved.finalAns,
    JSON.stringify(saved).slice(0, 90));
// เก็บเป็นรหัสประจำข้อ ไม่ใช่ลำดับ ไม่งั้นแทรกข้อใหม่แล้วความก้าวหน้าไปทับข้ออื่น
chk('บันทึกความก้าวหน้าด้วยรหัสประจำข้อ ไม่ใช่ลำดับ',
    saved.done.every(k => typeof k === 'string' && /^[a-z0-9-]+-\d\d-[0-9a-f]{8}$/.test(k))
    && Object.keys(saved.finalAns).every(k => typeof k === 'string' && !/^\d+$/.test(k)),
    JSON.stringify(saved.done));

// ---------- เฉลยล็อกด้วยรหัสผ่าน ----------
click($('#revealBtn'));
chk('กดดูเฉลยแล้วขอรหัสผ่าน', $('#pwOverlay').classList.contains('show'));
$('#pwInput').value = 'ผิด';
click($('#pwConfirmBtn'));
chk('รหัสผิดไม่เปิดเฉลย', !$('.answer').classList.contains('show'));
$('#pwInput').value = '2569';
click($('#pwConfirmBtn'));
chk('รหัสถูกเปิดเฉลย', $('.answer').classList.contains('show'));

// ---------- ป้ายบอกสาระที่คลังไม่ครอบคลุม ----------
// เหตุผลอยู่ใน docs/implementation-plan.md ข้อ 6.6 — ป้าย "ครบทุกตัวชี้วัด" บนวิชาที่
// ครอบคลุมครึ่งเดียวทำให้เด็กเตรียมสอบผิด ซึ่งเสียหายกว่าการไม่มีวิชานั้นเลย
{
  chk('วิชาที่ครอบคลุมครบ ไม่ขึ้นป้ายเตือน', !$('#courseGrid .c-gaps'),
      ($('#courseGrid .c-gaps') || {}).textContent);

  // ยังไม่มีวิชาไหนมีหัวข้อ practical จริง (มาถึงตอนเฟส 10) จึงป้อน gaps เข้า MANIFEST
  // ตรง ๆ เพื่อให้เส้นทางการวาดถูกเดินจริง ไม่ใช่โค้ดที่ไม่เคยถูกเรียก
  const faked = html.replace('const MANIFEST = [{"slug": "math-m1"',
                             'const MANIFEST = [{"gaps": ["พลศึกษา"], "slug": "math-m1"');
  if (faked === html) throw new Error('แทรก gaps เข้า MANIFEST ไม่สำเร็จ — รูปแบบเปลี่ยนไป');
  const g = new JSDOM(faked, { runScripts: 'dangerously', pretendToBeVisual: true,
                               url: 'https://tkosin.github.io/Thai-Exam-AI-Socratic-Tutor/' });
  const box = [...g.window.document.querySelectorAll('#courseGrid .course-card')]
    .find(c => c.textContent.includes('คณิตศาสตร์ ม.1'));
  const gap = box && box.querySelector('.c-gaps');
  chk('วิชาที่ไม่ครอบคลุมบางสาระ ขึ้นป้ายบอกตรง ๆ',
      !!gap && gap.textContent.includes('พลศึกษา'), gap && gap.textContent);
  chk('ป้ายบอกด้วยว่าทำไมถึงไม่มี',
      !!gap && /ปฏิบัติ/.test(gap.textContent), gap && gap.textContent);
  chk('วิชาอื่นที่ไม่มี gaps ยังไม่ขึ้นป้าย',
      [...g.window.document.querySelectorAll('#courseGrid .course-card')]
        .filter(c => c.querySelector('.c-gaps')).length === 1);
}

// ---------- คำอธิบายวิธีคิด: ต้องอ่านได้โดยไม่ต้องปลดล็อกเฉลย ----------
// เหตุผลของด่านนี้อยู่ใน docs/implementation-plan.md ข้อ 6.3 — คำอธิบายที่ล็อกไว้
// หลังรหัสผ่านที่นักเรียนไม่มี เท่ากับไม่มีคำอธิบาย
{
  const withEx = ALL_Q.filter(q => q.explain);
  chk('คลังมีข้อที่เติมคำอธิบายแล้ว', withEx.length > 0, `${withEx.length} ข้อ`);
  const target = withEx[0];
  const r = enterExam(load(), `${target.subject} ${target.grade}`);
  const rd = s => r.d.querySelector(s);
  const rclick = el => el.dispatchEvent(new r.w.Event('click'));
  const rtype = (el, v) => { el.value = v; el.dispatchEvent(new r.w.Event('input')); };
  const head = target.explain.slice(0, 30);

  chk('ยังไม่กดตรวจ ยังไม่เห็นคำอธิบาย', !rd('#checkResult .rexplain'));

  rtype(rd('#finalInput'), 'คำตอบที่ผิดแน่นอน 99999');
  rclick(rd('#checkBtn'));
  chk('ตอบผิดแล้วเห็นคำอธิบาย', (rd('#checkResult').textContent || '').includes(head),
      (rd('#checkResult').textContent || '').slice(0, 60));
  chk('เห็นคำอธิบายโดยไม่ต้องใส่รหัสผ่าน', !rd('#answerBox').classList.contains('show'));
  chk('คำอธิบายไม่ได้แอบบอกตัวเฉลย',
      !(rd('#checkResult .rexplain').textContent || '').includes(`เฉลย: ${target.answer}`));

  rtype(rd('#finalInput'), target.answer);
  rclick(rd('#checkBtn'));
  chk('ตอบถูกก็ยังเห็นคำอธิบาย', (rd('#checkResult').textContent || '').includes(head),
      rd('#checkResult').className);

  // ข้อที่ยังไม่มีคำอธิบาย (คลังเดิม 5,175 ข้อ) ต้องไม่ขึ้นกล่องเปล่า
  const plain = enterExam(load(), 'คณิตศาสตร์ ม.1');
  const pd = s => plain.d.querySelector(s);
  pd('#finalInput').value = 'ผิดแน่นอน 99999';
  pd('#finalInput').dispatchEvent(new plain.w.Event('input'));
  pd('#checkBtn').dispatchEvent(new plain.w.Event('click'));
  chk('ข้อที่ไม่มีคำอธิบาย ไม่ขึ้นกล่องเปล่า',
      !pd('#checkResult .rexplain') && pd('#checkResult').className.includes('show'),
      pd('#checkResult').className);
}

// ---------- โหลดข้อมูลที่บันทึกไว้กลับมาได้ ----------
{
  const key = Object.keys(w.localStorage).find(k => PROGRESS.test(k));
  const r = enterExam(load({ key, value: {
    done: [QID(0), QID(5)], work: { [QID(0)]: ['a', 'b', 'c'] }, finalAns: { [QID(0)]: '42' }, checked: {} } }));
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

// ---------- ย้ายความก้าวหน้าแบบเก่า (อ้างลำดับข้อ) มาเป็นแบบอ้างรหัสประจำข้อ ----------
{
  // ผู้เรียนที่บันทึกไว้ก่อนเปลี่ยนระบบ ต้องไม่เสียงานที่ทำมา
  const r = enterExam(load({ key: 'funnymath-m1-v5', value: {
    done: [0, 5], work: { 0: ['เก่า1', 'เก่า2'] }, finalAns: { 0: '42' }, checked: { 0: 'ok' }
  }}));
  const rd = s => r.d.querySelector(s);
  chk('ของเดิมย้ายมาแล้ว: วิธีทำครบ', r.d.querySelectorAll('#workLines .work-line').length === 2,
      r.d.querySelectorAll('#workLines .work-line').length);
  chk('ของเดิมย้ายมาแล้ว: คำตอบครบ', rd('#finalInput').value === '42', rd('#finalInput').value);
  chk('ของเดิมย้ายมาแล้ว: นับข้อที่ทำแล้วถูก',
      rd('#progressLabel').textContent.includes('ทำแล้ว 2'), rd('#progressLabel').textContent);
  const now = JSON.parse(r.w.localStorage.getItem('funnymath-m1-v6') || '{}');
  chk('ย้ายแล้วเขียนกลับเป็นรหัสประจำข้อ',
      Array.isArray(now.done) && now.done.length === 2 && now.done.includes(QID(0)),
      JSON.stringify(now.done));
  chk('ไม่ลบของเดิมทิ้ง เผื่อกู้เอง', !!r.w.localStorage.getItem('funnymath-m1-v5'), '');
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
    done: [QID(0), QID(1)], work: {}, finalAns: {},
    checked: { [QID(1)]: 'ok', [QID(2)]: 'no', [QID(3)]: 'manual' }
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
  // จำนวนข้อรายหน่วยต้องตรงกับคลังจริง และรวมกันต้องเท่ากับยอดของวิชานั้น
  {
    const card = rall('#courseGrid .course-card')[0];
    const name = card.querySelector('.c-name').textContent.trim();
    const [subject, grade] = [name.slice(0, name.lastIndexOf(' ')), name.slice(name.lastIndexOf(' ') + 1)];
    const mine = ALL_Q.filter(q => q.subject === subject && q.grade === grade);
    const want = {};
    mine.forEach(q => { want[q.unit] = (want[q.unit] || 0) + 1; });
    const got = [...card.querySelectorAll('.c-units button')]
      .map(b => +b.querySelector('.u-c').textContent);
    const wantList = Object.keys(want).map(Number).sort((a, b) => a - b).map(u => want[u]);
    chk('ทางลัดหน่วยบอกจำนวนข้อของหน่วยนั้น',
        got.length === wantList.length && got.every((n, i) => n === wantList[i]),
        `${got.join('/')} vs ${wantList.join('/')}`);
    chk('จำนวนข้อรายหน่วยรวมกันเท่ากับยอดของวิชา',
        got.reduce((a, b) => a + b, 0) === mine.length,
        `${got.reduce((a, b) => a + b, 0)} vs ${mine.length}`);
    chk('title ของทางลัดบอกทั้งชื่อหน่วยและจำนวนข้อ',
        /หน่วยที่ \d+: .+ · \d+ ข้อ$/.test(card.querySelector('.c-units button').title),
        card.querySelector('.c-units button').title);
  }

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
  chk('บันทึกข้อล่าสุดไว้ด้วยรหัสประจำข้อ', typeof ui.lastId === 'string' && !!ui.lastId,
      JSON.stringify(ui.lastId));
  const back = load({ key: 'funnymath-ui-v1', value: { lastId: QID(5) } });
  chk('รีเฟรชแล้วยังมีปุ่มทำต่อ', !!back.d.querySelector('#resumeBtn'), '');
  chk('ปุ่มทำต่อชี้ไปข้อที่บันทึกไว้',
      /ข้อที่ 6/.test(back.d.querySelector('.resume .r-main').textContent),
      back.d.querySelector('.resume .r-main').textContent);
  const bad = load({ key: 'funnymath-ui-v1', value: { lastGidx: 999999 } });
  chk('ข้อล่าสุดที่ไม่มีอยู่จริงไม่ทำให้หน้าแรกพัง',
      !bad.d.querySelector('#resumeBtn') && !!bad.d.querySelector('#courseGrid .course-card'), '');
}

// ---------- จอมือถือ: เมนู ☰ และการไม่ล้นแนวนอน ----------
{
  const r = load();
  const rd = s => r.d.querySelector(s);
  const rclick = el => el.dispatchEvent(new r.w.Event('click'));
  // สองเคสล่างพึ่งการ bubble ของอีเวนต์ (ตัวดักอยู่ที่ #headerActions และ document)
  // Event ธรรมดาไม่ bubble ต่างจากการคลิกจริงในเบราว์เซอร์ จึงต้องสั่งให้ bubble
  const rclickUp = el => el.dispatchEvent(new r.w.Event('click', { bubbles: true }));
  const navOpen = () => r.d.body.classList.contains('nav-open');
  const nav = rd('#navToggle');

  // การ์ดวิชาเคยล็อกความกว้างขั้นต่ำไว้ 420px จอ 390px จึงเลื่อนแนวนอนได้
  chk('คอลัมน์การ์ดวิชาไม่กว้างเกินจอ',
      /grid-template-columns:\s*repeat\(auto-fit,\s*minmax\(min\(420px,\s*100%\)/.test(html), '');
  chk('มีชุดกฎสำหรับจอแคบที่ยุบปุ่มเป็นเมนู',
      /@media \(max-width:760px\)/.test(html) && /body\.nav-open \.header-actions\{/.test(html.replace(/\s*\n\s*/g, '')), '');

  chk('มีปุ่ม ☰ ในหัวเรื่อง', !!nav && nav.getAttribute('aria-controls') === 'headerActions', '');
  chk('หน้าแรกซ่อนปุ่ม ☰ ไว้ (เมนูจะว่าง)', nav.classList.contains('hide'), nav.className);

  enterExam(r);
  chk('เข้าหน้าข้อสอบแล้วปุ่ม ☰ โผล่', !nav.classList.contains('hide'), nav.className);
  chk('ยังไม่กดเมนู → ยังไม่กาง',
      !navOpen() && nav.getAttribute('aria-expanded') === 'false', '');

  rclick(nav);
  chk('กด ☰ แล้วกางเมนู',
      navOpen() && nav.getAttribute('aria-expanded') === 'true', '');
  chk('กางแล้วไอคอนเปลี่ยนเป็น ✕', nav.textContent.trim() === '✕', nav.textContent);
  // ปุ่มในเมนูต้องเป็นชุดเดียวกับเดิม ไม่ใช่ปุ่มก๊อปที่ทำให้ id ซ้ำ
  const ids = ['homeBtn', 'filterToggle', 'overviewBtn', 'aiSetupBtn', 'printExamBtn', 'printAnswerBtn'];
  chk('เมนูใช้ปุ่มชุดเดิมครบ 6 ปุ่ม ไม่มี id ซ้ำ',
      ids.every(id => r.d.querySelectorAll('#' + id).length === 1
                   && rd('#headerActions #' + id)), '');

  rclickUp(rd('#overviewBtn'));
  chk('กดปุ่มในเมนูแล้วเมนูปิดเอง', !navOpen(), '');
  chk('และคำสั่งนั้นทำงานจริง', rd('#overviewOverlay').classList.contains('show'), '');
  rclick(rd('#overviewOverlay .modal-close'));

  rclick(nav);
  r.d.dispatchEvent(new r.w.KeyboardEvent('keydown', { key: 'Escape' }));
  chk('Esc ปิดเมนู', !navOpen() && nav.textContent.trim() === '☰', '');

  rclick(nav);
  rclickUp(rd('#examCard'));
  chk('กดนอกหัวเรื่องปิดเมนู', !navOpen(), '');

  rclick(nav);
  rclick(rd('#homeBtn'));
  chk('กลับหน้าแรกแล้วเมนูปิดและซ่อนปุ่ม ☰',
      !navOpen() && nav.classList.contains('hide'), '');
}

// ---------- ติวเตอร์ AI ----------
// ยัด fetch ปลอมที่คืนสตรีม SSE ให้ ไม่ต้องต่อเน็ตจริงและไม่ต้องมีคีย์จริง
function loadTutor(seeds, reply = 'ลองอ่านโจทย์อีกครั้ง โจทย์ให้อะไรมาบ้าง?', wire = 'anthropic') {
  const sent = [];
  // สตรีมคำตอบในรูปแบบ SSE ของแต่ละเจ้า — โครง JSON ต่างกันหมด
  const sse = wire === 'openai'
    ? [{ choices: [{ delta: { content: reply } }] },
       { choices: [{ delta: {}, finish_reason: 'stop' }] }]
        .map(e => `data: ${JSON.stringify(e)}\n\n`).join('') + 'data: [DONE]\n\n'
    : wire === 'gemini'
    ? [{ candidates: [{ content: { parts: [{ text: reply }] } }] },
       { candidates: [{ content: { parts: [] }, finishReason: 'STOP' }] }]
        .map(e => `data: ${JSON.stringify(e)}\n\n`).join('')
    : [
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
    url: 'https://tkosin.github.io/Thai-Exam-AI-Socratic-Tutor/',
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
  const card = [...r.d.querySelectorAll('#courseGrid .course-card')]
    .find(c => c.textContent.includes('คณิตศาสตร์ ม.1'));
  card.querySelector('.c-go').dispatchEvent(new r.w.Event('click'));
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
  // jsdom จัดเลย์เอาต์ไม่ได้ จึงตรวจที่ "กฎ CSS" แทน — เคยพลาดตอนวัดจริงเพราะแผงยังเลื่อนไม่จบ
  // (transform:translateX(100%) -> none ใช้เวลา .22s) จึงกันไว้ว่ากฎยังอยู่ครบ
  const css = html.replace(/\s*\n\s*/g, ' ');
  chk('จอแคบกว่า 1100px แผงพี่หลวงกางเต็มความกว้าง',
      /@media \(max-width:1100px\)\{ :root\{ --tutorw:100%; \}/.test(css), '');
  chk('แผงตรึงขอบขวาและซ่อนด้วยการเลื่อนออกนอกจอ',
      /\.tutor-panel\{[^}]*position:fixed[^}]*right:0[^}]*width:var\(--tutorw\)/.test(css)
      && /\.tutor-panel\{[^}]*transform:translateX\(100%\)/.test(css)
      && /\.tutor-panel\.show\{ transform:none;/.test(css), '');
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
    chk('พรอมป์ระบบบอกกติกาการวาดรูป และย้ำว่าวาดเฉพาะเมื่อจำเป็น',
        /## วาดรูปประกอบได้ \(ใช้เมื่อจำเป็นเท่านั้น\)/.test(req.body.system)
        && /ส่วนใหญ่ไม่ต้องวาด/.test(req.body.system)
        && /```svg/.test(req.body.system), '');
    chk('พรอมป์ระบบบอกสัญกรณ์คณิตศาสตร์ที่หน้าเว็บจัดรูปได้ และห้าม LaTeX',
        /ยกกำลังใช้ \^/.test(req.body.system) && /ห้ามใช้ LaTeX ทุกชนิด/.test(req.body.system), '');
    chk('แผงและปุ่มเรียกชื่อพี่หลวงตรงกัน',
        /พี่หลวง/.test(t2.d.querySelector('.tp-title').textContent)
        && /พี่หลวง/.test(t2.d.querySelector('#tutorToggle').textContent), '');
    // ตรวจเฉพาะ "ส่วนโจทย์" — ท้ายพรอมป์มีตัวอย่าง <svg> ของกติกาการวาดรูปอยู่ด้วย
    const qBlock = (req.body.system.split('## เฉลย')[0] || '');
    chk('พรอมป์ระบบไม่มีแท็ก HTML ของโจทย์ติดไปด้วย',
        !/<(div|span|svg|sup|br|table)\b/.test(qBlock), qBlock.slice(-80));
    chk('คำตอบติวเตอร์ขึ้นในกล่องแช็ต',
        /ลองอ่านโจทย์อีกครั้ง/.test((t2.d.querySelector('.bubble.ai') || {}).textContent || ''), '');
    chk('ถามแล้วขั้นคำใบ้ขยับเป็น 2',
        /ขั้นที่ 2 \/ 7/.test(t2.d.querySelector('.tutor-rung').textContent),
        t2.d.querySelector('.tutor-rung').textContent);

    const saved = JSON.parse(t2.w.localStorage.getItem('funnymath-chat-v2') || '{}');
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
    // ---------- รูป SVG ที่ติวเตอร์วาด ----------
    // sanitizer พลาดเมื่อไร = โค้ดของโมเดลรันในโดเมนเดียวกับที่เก็บ API key
    // เทสต์ชุดนี้จึงยิงเพย์โหลดโจมตีจริง แล้วตรวจว่าไม่มีอะไรรอด
    const drawn = async (reply) => {
      const r = loadTutor(opened, reply);
      r.d.querySelector('#tutorInput').value = 'ขอรูป';
      tclick(r, '#tutorSend');
      await waitFor(() => (r.d.querySelector('.bubble.ai') || {}).textContent
        || r.d.querySelector('.bubble.ai .bubble-fig'));
      const bubble = r.d.querySelector('.bubble.ai');
      const svg = bubble.querySelector('svg');
      return {
        html: bubble.innerHTML,
        svg,
        bad: !!bubble.querySelector('.bubble-fig.bad'),
        tags: svg ? [...svg.querySelectorAll('*')].map(e => e.localName) : [],
        attrs: svg ? [...svg.querySelectorAll('*')].concat(svg)
          .flatMap(e => [...e.attributes].map(a => a.name)) : [],
      };
    };

    const ok = await drawn('ดูรูปนี้ครับ\n```svg\n<svg viewBox="0 0 320 120">' +
      '<defs><marker id="a" refX="6" refY="3" markerWidth="8" markerHeight="6" orient="auto">' +
      '<polygon points="0 0, 8 3, 0 6" fill="#C0392B"/></marker></defs>' +
      '<line x1="20" y1="60" x2="300" y2="60" stroke="#1E3A5F" stroke-width="2" marker-end="url(#a)"/>' +
      '<text x="86" y="45" font-size="13">-2</text></svg>\n```\nเห็นภาพไหมครับ');
    chk('ติวเตอร์แนบรูปได้ และรูปขึ้นเป็น <svg> จริง', !!ok.svg && !ok.bad, ok.tags.join(','));
    chk('รูปเก็บแท็กที่อนุญาตไว้ครบ',
        ['marker', 'polygon', 'line', 'text'].every(t => ok.tags.includes(t)), ok.tags.join(','));
    chk('แอตทริบิวต์ที่แยกตัวพิมพ์ไม่เพี้ยน (viewBox/refX/markerWidth)',
        ok.attrs.includes('viewBox') && ok.attrs.includes('refX') && ok.attrs.includes('markerWidth'),
        ok.attrs.join(','));
    chk('อนุญาต marker-end ที่อ้างในรูปเดียวกัน', ok.attrs.includes('marker-end'), '');
    chk('ข้อความรอบรูปยังแสดงตามปกติ', /ดูรูปนี้ครับ/.test(ok.html) && /เห็นภาพไหมครับ/.test(ok.html), '');

    const ATTACKS = [
      ['script ในรูป', '<svg viewBox="0 0 10 10"><script>window.__pwned=1<\/script><rect width="5" height="5"/></svg>', 'script'],
      ['onload บน svg', '<svg viewBox="0 0 10 10" onload="window.__pwned=1"><rect width="5" height="5"/></svg>', 'onload'],
      ['onclick บนรูปทรง', '<svg viewBox="0 0 10 10"><rect width="9" height="9" onclick="window.__pwned=1"/></svg>', 'onclick'],
      ['foreignObject', '<svg viewBox="0 0 10 10"><foreignObject><img src=x onerror="window.__pwned=1"></foreignObject></svg>', 'foreignobject'],
      ['xlink:href javascript:', '<svg viewBox="0 0 10 10"><a xlink:href="javascript:window.__pwned=1"><text x="1" y="5">กด</text></a></svg>', 'javascript:'],
      ['use ดึงจากภายนอก', '<svg viewBox="0 0 10 10"><use href="https://evil.test/x.svg#a"/></svg>', 'evil.test'],
      ['animate เปลี่ยน href', '<svg viewBox="0 0 10 10"><animate attributeName="href" values="javascript:1"/></svg>', 'animate'],
      ['style/fill url() ภายนอก', '<svg viewBox="0 0 10 10"><rect width="9" height="9" style="x:1" fill="url(https://evil.test/y)"/></svg>', 'evil.test'],
      ['image ภายนอก', '<svg viewBox="0 0 10 10"><image href="https://evil.test/t.png" width="9" height="9"/></svg>', 'evil.test'],
      ['set + onbegin', '<svg viewBox="0 0 10 10"><set onbegin="window.__pwned=1"/><circle cx="5" cy="5" r="4"/></svg>', 'onbegin'],
    ];
    for (const [name, payload, needle] of ATTACKS) {
      const r = await drawn('```svg\n' + payload + '\n```');
      const leaked = r.html.toLowerCase().includes(needle)
        || r.tags.some(t => ['script', 'foreignobject', 'use', 'image', 'animate', 'set', 'a'].includes(t))
        || r.attrs.some(a => /^on/i.test(a) || /href|style/i.test(a));
      chk('กัน XSS ในรูป: ' + name, !leaked, r.html.slice(0, 90));
    }
    chk('ไม่มี window.__pwned หลุดมาจากเพย์โหลดใด ๆ',
        typeof loadTutor(opened, 'x').w.__pwned === 'undefined', '');

    // ระหว่างสตรีมรูปยังวาดไม่จบ ต้องไม่โชว์ SVG พัง ๆ
    const half = loadTutor(opened, 'กำลังอธิบาย\n```svg\n<svg viewBox="0 0 320 120"><line x1="0"');
    half.d.querySelector('#tutorInput').value = 'ขอรูป';
    tclick(half, '#tutorSend');
    await waitFor(() => (half.d.querySelector('.bubble.ai') || {}).textContent);
    chk('รูปที่ยังวาดไม่จบไม่ถูกแสดงเป็น SVG พัง ๆ',
        !half.d.querySelector('.bubble.ai svg'), half.d.querySelector('.bubble.ai').innerHTML.slice(0, 80));

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

    // ---------- ติวเตอร์ตรวจโจทย์/เฉลยให้ด้วย ----------
    const FLAW = '⟪ตรวจพบปัญหาในข้อสอบ⟫';

    // พรอมป์ต้องสั่งให้ตรวจ และสั่งว่า "ถูกแล้วไม่ต้องพูดถึง"
    const chk1 = loadTutor(opened);
    chk1.d.querySelector('#tutorInput').value = 'เริ่มเลย';
    tclick(chk1, '#tutorSend');
    await waitFor(() => chk1.sent.length);
    const sys = chk1.sent[0].body.system;
    chk('พรอมป์สั่งให้ตรวจโจทย์กับเฉลยก่อนตอบ',
        /ตรวจโจทย์กับเฉลยก่อนตอบทุกครั้ง/.test(sys) && sys.includes(FLAW), '');
    chk('พรอมป์สั่งว่าถ้าถูกต้องไม่ต้องบอกนักเรียน',
        /ไม่ต้องพูดถึงเรื่องนี้เลย สอนตามปกติ/.test(sys), '');
    chk('พรอมป์กันไม่ให้ใช้การทักเป็นข้ออ้างเฉลยก่อนขั้น',
        /ไม่ใช่ข้ออ้างให้บอกคำตอบก่อนถึงขั้นที่อนุญาต/.test(sys), '');
    chk('พรอมป์สั่งไม่ให้ตัดสินข้อที่มีรูปประกอบ',
        /ห้ามตัดสินว่าโจทย์\/เฉลยผิด/.test(sys), '');

    // ตอบปกติ (ไม่ทัก) -> ต้องไม่มีกล่องเตือนโผล่มาเอง
    chk('คำตอบปกติไม่ขึ้นกล่องเตือน', !chk1.d.querySelector('.bubble-flaw'), '');

    // ทักว่าเฉลยผิด -> ตัดบรรทัดแรกออกมาเป็นกล่องเตือน ที่เหลือยังเป็นคำสอนตามปกติ
    const flaw = loadTutor(opened,
      FLAW + ' เฉลยบอกว่า 22 แต่ (-52) - (-74) ได้ 22 จริง ๆ แล้วโจทย์พิมพ์ตกไป\n' +
      'ไม่เป็นไรครับน้อง ลองดูว่าโจทย์ถามหาอะไรก่อน');
    flaw.d.querySelector('#tutorInput').value = 'ข้อนี้งงครับ';
    tclick(flaw, '#tutorSend');
    await waitFor(() => flaw.d.querySelector('.bubble-flaw'));
    const warn = flaw.d.querySelector('.bubble-flaw');
    chk('ติวเตอร์ทักว่าเฉลยผิด -> ขึ้นกล่องเตือน', !!warn, '');
    chk('กล่องเตือนมีคำอธิบายว่าอะไรผิด',
        /โจทย์พิมพ์ตกไป/.test(warn.textContent), warn.textContent.slice(0, 50));
    chk('ตัวคั่นไม่หลุดออกมาให้นักเรียนเห็น',
        !flaw.d.querySelector('.bubble.ai').textContent.includes('⟪'),
        flaw.d.querySelector('.bubble.ai').textContent.slice(0, 40));
    chk('คำสอนที่เหลือยังแสดงตามปกติ',
        /ลองดูว่าโจทย์ถามหาอะไรก่อน/.test(flaw.d.querySelector('.bubble.ai').textContent), '');

    // ตัวคั่นกลางคำตอบต้องไม่ถูกตีความว่าเป็นการทัก (กันโมเดล/นักเรียนหลอกให้ขึ้นกล่อง)
    const mid = loadTutor(opened, 'ลองคิดดูครับ ' + FLAW + ' อันนี้เป็นแค่ข้อความ');
    mid.d.querySelector('#tutorInput').value = 'ถาม';
    tclick(mid, '#tutorSend');
    await waitFor(() => (mid.d.querySelector('.bubble.ai') || {}).textContent);
    chk('ตัวคั่นกลางคำตอบไม่นับเป็นการทัก',
        !mid.d.querySelector('.bubble-flaw'), '');

    // ---------- หลายผู้ให้บริการ: OpenAI · Gemini · OpenAI-compatible ----------
    // คีย์เก็บแยกเจ้าในรูปแบบใหม่ ของเก่า {key, model} ต้องย้ายให้เองตาม prefix ของคีย์
    const NEWKEY = cfg => ({ key: 'funnymath-ai-v1', value: cfg });

    // OpenAI: Chat Completions + Bearer + system เป็นข้อความแรก + max_completion_tokens
    const oa = loadTutor([...opened, NEWKEY({
      provider: 'openai', keys: { openai: 'sk-openai-test' },
      models: { openai: 'gpt-5-mini' } })], 'คำถามนำจาก GPT', 'openai');
    oa.d.querySelector('#tutorInput').value = 'ถาม GPT';
    tclick(oa, '#tutorSend');
    await waitFor(() => oa.sent.length);
    const oaReq = oa.sent[0];
    chk('OpenAI → เรียก /v1/chat/completions ด้วย Bearer key',
        oaReq.url === 'https://api.openai.com/v1/chat/completions'
        && oaReq.headers.authorization === 'Bearer sk-openai-test'
        && !('x-api-key' in oaReq.headers) && !('anthropic-version' in oaReq.headers),
        oaReq.url);
    chk('OpenAI → system เป็นข้อความแรก และใช้ max_completion_tokens',
        oaReq.body.messages[0].role === 'system'
        && /พี่หลวง/.test(oaReq.body.messages[0].content)
        && oaReq.body.max_completion_tokens === 4000 && !('max_tokens' in oaReq.body)
        && oaReq.body.model === 'gpt-5-mini' && oaReq.body.reasoning_effort === 'low',
        JSON.stringify(Object.keys(oaReq.body)));
    await waitFor(() => /คำถามนำจาก GPT/.test(oa.d.querySelector('.bubble.ai')?.textContent || ''));
    chk('OpenAI → สตรีมรูปแบบ delta.content ขึ้นเป็นคำตอบ',
        /คำถามนำจาก GPT/.test(oa.d.querySelector('.bubble.ai').textContent), '');

    // Gemini: streamGenerateContent + x-goog-api-key + systemInstruction + role user/model
    const gm = loadTutor([...opened, NEWKEY({
      provider: 'gemini', keys: { gemini: 'AIza-test' },
      models: { gemini: 'gemini-2.5-flash' } })], 'คำถามนำจาก Gemini', 'gemini');
    gm.d.querySelector('#tutorInput').value = 'ถาม Gemini';
    tclick(gm, '#tutorSend');
    await waitFor(() => gm.sent.length);
    const gmReq = gm.sent[0];
    chk('Gemini → เรียก streamGenerateContent ของโมเดลที่เลือกแบบ SSE',
        /generativelanguage\.googleapis\.com\/v1beta\/models\/gemini-2\.5-flash:streamGenerateContent\?alt=sse/.test(gmReq.url)
        && gmReq.headers['x-goog-api-key'] === 'AIza-test', gmReq.url);
    chk('Gemini → ส่ง systemInstruction แยก และปิด thinking ของ Flash',
        /พี่หลวง/.test(gmReq.body.systemInstruction.parts[0].text)
        && gmReq.body.contents[0].role === 'user'
        && gmReq.body.generationConfig.maxOutputTokens === 4000
        && gmReq.body.generationConfig.thinkingConfig.thinkingBudget === 0,
        JSON.stringify(Object.keys(gmReq.body)));
    await waitFor(() => /คำถามนำจาก Gemini/.test(gm.d.querySelector('.bubble.ai')?.textContent || ''));
    chk('Gemini → สตรีมรูปแบบ candidates/parts ขึ้นเป็นคำตอบ',
        /คำถามนำจาก Gemini/.test(gm.d.querySelector('.bubble.ai').textContent), '');
    // ประวัติฝั่งเราเป็น user/assistant ต้องแปลงเป็น user/model ก่อนส่งให้ Gemini
    gm.d.querySelector('#tutorInput').value = 'ถามต่อ';
    tclick(gm, '#tutorSend');
    await waitFor(() => gm.sent.length === 2);
    chk('Gemini → บทบาท assistant ถูกแปลงเป็น model',
        gm.sent[1].body.contents.map(c => c.role).join(',') === 'user,model,user',
        gm.sent[1].body.contents.map(c => c.role).join(','));

    // OpenAI-compatible: base URL ของผู้ใช้ + max_tokens (ไม่ใช่ max_completion_tokens)
    const cu = loadTutor([...opened, NEWKEY({
      provider: 'custom', keys: { custom: 'k-any' },
      customBase: 'http://localhost:11434/v1/', customModel: 'llama3.3' })],
      'คำถามนำจากโมเดลในเครื่อง', 'openai');
    cu.d.querySelector('#tutorInput').value = 'ถามในเครื่อง';
    tclick(cu, '#tutorSend');
    await waitFor(() => cu.sent.length);
    const cuReq = cu.sent[0];
    chk('Custom → ต่อ /chat/completions ท้าย base URL (ตัด / ซ้ำ) และใช้ max_tokens',
        cuReq.url === 'http://localhost:11434/v1/chat/completions'
        && cuReq.body.model === 'llama3.3'
        && cuReq.body.max_tokens === 4000 && !('max_completion_tokens' in cuReq.body)
        && !('reasoning_effort' in cuReq.body),
        cuReq.url);

    // ย้ายค่าที่เก็บแบบเก่า — คีย์ OpenAI ที่เคยใส่ไว้ต้องไปอยู่เจ้า openai ไม่ใช่ anthropic
    const mig = loadTutor([...opened,
      { key: 'funnymath-ai-v1', value: { key: 'sk-proj-old', model: 'claude-opus-5' } }],
      'ok', 'openai');
    mig.d.querySelector('#tutorInput').value = 'ถาม';
    tclick(mig, '#tutorSend');
    await waitFor(() => mig.sent.length);
    chk('คีย์แบบเก่าที่เป็นของ OpenAI → ย้ายไปเรียก OpenAI ให้เอง',
        mig.sent[0].url.includes('api.openai.com')
        && mig.sent[0].headers.authorization === 'Bearer sk-proj-old', mig.sent[0].url);

    // หน้าต่างตั้งค่า: มีตัวเลือกผู้ให้บริการครบ และสลับแล้วรายการโมเดลเปลี่ยนตาม
    const ui = loadTutor([...opened, NEWKEY({ provider: 'anthropic',
      keys: { anthropic: 'sk-ant-x' }, models: {} })]);
    tclick(ui, '#aiSetupBtn');
    const provSel = ui.d.querySelector('#aiProviderSelect');
    chk('หน้าตั้งค่ามีผู้ให้บริการครบ 4 เจ้า',
        [...provSel.options].map(o => o.value).join(',') === 'anthropic,openai,gemini,custom',
        [...provSel.options].map(o => o.value).join(','));
    provSel.value = 'gemini';
    provSel.dispatchEvent(new ui.w.Event('change'));
    chk('สลับเป็น Gemini → รายการโมเดลเป็นของ Gemini และช่องคีย์บอก AIza',
        [...ui.d.querySelector('#aiModelSelect').options].every(o => o.value.startsWith('gemini-'))
        && ui.d.querySelector('#aiKeyInput').placeholder === 'AIza...', '');
    provSel.value = 'custom';
    provSel.dispatchEvent(new ui.w.Event('change'));
    chk('สลับเป็น custom → โชว์ช่อง Base URL/ชื่อโมเดล แทนรายการโมเดล',
        ui.d.querySelector('#aiCustomFields').style.display !== 'none'
        && ui.d.querySelector('#aiStdFields').style.display === 'none', '');
    // สลับกลับมา — คีย์ Anthropic ที่ใส่ไว้ต้องยังอยู่
    provSel.value = 'anthropic';
    provSel.dispatchEvent(new ui.w.Event('change'));
    chk('สลับผู้ให้บริการไปมาแล้วคีย์ของแต่ละเจ้าไม่หาย',
        ui.d.querySelector('#aiKeyInput').value === 'sk-ant-x', ui.d.querySelector('#aiKeyInput').value);

    // ชุดโหลดรายวิชาก็เป็น async เหมือนกัน ต้องรอให้จบก่อนสรุปผล
    LAZY.then(report, e => { chk('ชุดเทสต์โหลดรายวิชาทำงานจบ', false, e && e.message); report(); });
  })().catch(e => {
    chk('ชุดเทสต์ติวเตอร์ AI ทำงานจบ', false, e && e.message);
    LAZY.then(report, report);
  });
}

// ---------- โหลดข้อสอบรายวิชา (index.html ตัวจริงที่เสิร์ฟออนไลน์) ----------
// บล็อกนี้ใช้ shell จริงซึ่ง QUESTIONS ว่าง แล้ว stub fetch ให้คืน data/<slug>.json
function loadShell({ fail = false, seeds = [] } = {}) {
  const asked = [];
  const dom = new JSDOM(shellHtml, {
    runScripts: 'dangerously',
    pretendToBeVisual: true,
    url: 'https://tkosin.github.io/Thai-Exam-AI-Socratic-Tutor/',
    beforeParse(w) {
      seeds.forEach(x => w.localStorage.setItem(x.key, JSON.stringify(x.value)));
      w.fetch = (url) => {
        asked.push(url);
        if (fail) return Promise.resolve({ ok: false, status: 503 });
        const slug = String(url).replace(/^data\//, '').replace(/\.json$/, '');
        const file = path.join(DATA_DIR, slug + '.json');
        if (!fs.existsSync(file)) return Promise.resolve({ ok: false, status: 404 });
        const body = JSON.parse(fs.readFileSync(file, 'utf8'));
        return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(body) });
      };
    },
  });
  dom.virtualConsole.on('jsdomError', e => errs.push(e.message));
  return { dom, d: dom.window.document, w: dom.window, asked };
}

// บล็อกนี้ต้องรอ fetch ที่ stub ไว้ จึงเป็น async แล้วค่อยเรียก report() ตอนจบ
LAZY = (async () => {
  const r = loadShell();
  const rd = s => r.d.querySelector(s);
  const rall = s => [...r.d.querySelectorAll(s)];
  const MANIFEST = JSON.parse(shellHtml.match(/const MANIFEST = (\[[\s\S]*?\]);/)[1]);

  // หน้าแรกต้องครบโดยยังไม่โหลดข้อสอบสักวิชา
  chk('เปิดเว็บมาแล้วยังไม่โหลดข้อสอบสักไฟล์', r.asked.length === 0, r.asked.join());
  const cards = rall('#courseGrid .course-card');
  // นับจาก MANIFEST เหมือนกัน — คลังเพิ่มวิชาได้ ไม่ควรต้องมาแก้เลขในเทสต์
  chk('หน้าแรกแสดงครบทุกวิชาจาก MANIFEST', cards.length === MANIFEST.length,
      `${cards.length} จาก ${MANIFEST.length}`);
  chk('การ์ดวิชาบอกจำนวนข้อและจำนวนหน่วยได้โดยไม่โหลดข้อสอบ',
      /\d+ ข้อ · \d+ หน่วย/.test(cards[0].querySelector('.c-count').textContent),
      cards[0].querySelector('.c-count').textContent);
  const chips = cards[0].querySelectorAll('.c-units button');
  chk('ทางลัดหน่วยและจำนวนข้อรายหน่วยมาจาก MANIFEST',
      chips.length > 0 && +chips[0].querySelector('.u-c').textContent > 0,
      chips.length + ' หน่วย');
  // เทียบกับผลรวมของ MANIFEST ไม่ใช่ตัวเลขที่พิมพ์ไว้ตายตัว — คลังโตทุกเฟส
  const manifestTotal = MANIFEST.reduce((n, c) => n + c.count, 0);
  chk('ยอดรวมทุกวิชาบนหัวเรื่องถูกต้อง',
      rd('#progressLabel').textContent.includes(manifestTotal.toLocaleString('en-US')),
      rd('#progressLabel').textContent);

  // กดเข้าวิชา -> โหลดเฉพาะไฟล์ของวิชานั้น
  rall('#courseGrid .c-go')[0].dispatchEvent(new r.w.Event('click'));
  chk('กดเข้าวิชาแล้วขึ้นสถานะกำลังโหลด', !!rd('.course-load'), '');
  chk('ยิงคำขอไปไฟล์ของวิชานั้นไฟล์เดียว',
      r.asked.length === 1 && /^data\/[a-z0-9-]+\.json$/.test(r.asked[0]), r.asked.join());
  await waitFor(() => !!r.d.querySelector('#examCard .qtext'), 200);
  chk('โหลดเสร็จแล้ววาดข้อสอบให้', !!rd('#examCard .qtext'), '');
  chk('เลขข้อนับใหม่ถูกต้องหลังโหลด', /ข้อ 1 \/ \d+/.test(rd('#navCenter').textContent),
      rd('#navCenter').textContent);
  chk('กลับไปกดวิชาเดิมซ้ำไม่โหลดใหม่', (() => {
      const before = r.asked.length;
      rd('#homeBtn').dispatchEvent(new r.w.Event('click'));
      rall('#courseGrid .c-go')[0].dispatchEvent(new r.w.Event('click'));
      return r.asked.length === before;
    })(), '');

  // ความก้าวหน้าของวิชาที่ยังไม่โหลด ต้องนับได้จากรหัสข้อที่บันทึกไว้
  const all = JSON.parse(fs.readFileSync(path.join(DATA_DIR, 'math-m3.json'), 'utf8'));
  const prog = loadShell({ seeds: [{ key: 'funnymath-m1-v6', value: {
    done: [all[0].id, all[1].id, all[2].id], work: {}, finalAns: {},
    checked: { [all[0].id]: 'ok', [all[1].id]: 'no' } } }] });
  chk('นับความก้าวหน้าของวิชาที่ยังไม่โหลดได้', prog.asked.length === 0
      && /ทำแล้ว 3/.test(prog.d.querySelector('#progressLabel').textContent),
      prog.d.querySelector('#progressLabel').textContent);
  const m3 = [...prog.d.querySelectorAll('#courseGrid .course-card')]
    .find(c => /ม\.3/.test(c.querySelector('.c-name').textContent));
  chk('การ์ดวิชาบอกถูก/ผิดของวิชาที่ยังไม่โหลดได้',
      /ทำแล้ว 3/.test(m3.querySelector('.c-stat').textContent)
      && /ถูก 1/.test(m3.querySelector('.c-stat').textContent)
      && /ผิด 1/.test(m3.querySelector('.c-stat').textContent),
      m3.querySelector('.c-stat').textContent.replace(/\s+/g, ' '));
  // ปุ่มทำต่อชี้ไปวิชาที่ยังไม่โหลดได้ เพราะอ่านวิชา/หน่วยจากตัวรหัสข้อ
  const r2 = loadShell({ seeds: [{ key: 'funnymath-ui-v1',
    value: { lastId: all[0].id, lastNo: 7 } }] });
  chk('ปุ่มทำต่อชี้ไปข้อในวิชาที่ยังไม่โหลด',
      !!r2.d.querySelector('#resumeBtn') && r2.asked.length === 0
      && /ข้อที่ 7/.test(r2.d.querySelector('.resume .r-main').textContent),
      r2.d.querySelector('.resume .r-main').textContent);

  // โหลดไม่สำเร็จต้องบอกผู้เรียนและให้ลองใหม่ได้ ไม่ใช่ค้างอยู่ที่ "กำลังโหลด"
  const bad = loadShell({ fail: true });
  [...bad.d.querySelectorAll('#courseGrid .c-go')][0].dispatchEvent(new bad.w.Event('click'));
  await waitFor(() => !!bad.d.querySelector('.course-load.bad'), 200);
  chk('โหลดไม่สำเร็จ -> บอกผู้เรียนพร้อมปุ่มลองใหม่',
      !!bad.d.querySelector('.course-load.bad') && !!bad.d.querySelector('#retryCourseBtn'),
      (bad.d.querySelector('#examCard') || {}).textContent);
})();

// ---------- ผลลัพธ์ ----------
// เทสต์ของติวเตอร์ AI เป็น async (รอสตรีมคำตอบ) จึงสรุปผลเมื่อชุดนั้นจบ
function report() {
  const failed = T.filter(t => t[0] === 'FAIL');
  console.log(T.map(([s, n, e]) => `${s}  ${n}${s === 'FAIL' ? '   << ' + e : ''}`).join('\n'));
  console.log(`\n${T.length - failed.length}/${T.length} ผ่าน`);
  if (errs.length) console.log('JS ERRORS:\n' + errs.join('\n'));
  process.exit(failed.length || errs.length ? 1 : 0);
}
