/* ตรวจเลย์เอาต์บนขนาดจอจริงด้วยเบราว์เซอร์ — เสริมจาก tools/dom_test.cjs
 *
 * dom_test.cjs รันบน jsdom ซึ่ง "ไม่จัดเลย์เอาต์" จึงวัดความกว้าง/ตำแหน่งไม่ได้เลย
 * ตรวจได้แค่ว่ากฎ CSS ยังอยู่ครบ · ไฟล์นี้เปิดหน้าจริงในหลายขนาดจอแล้ววัดของจริง
 *
 * ไม่ได้อยู่ใน tools/check.sh เพราะต้องลง Playwright + เบราว์เซอร์ (~100 MB)
 * ซึ่งหนักเกินไปสำหรับด่านตรวจก่อน push · รันเองเวลาที่แก้ CSS เลย์เอาต์
 *
 *   npm install playwright --no-save && npx playwright install chromium
 *   node tools/responsive_check.js
 *   SHOT_DIR=./shots node tools/responsive_check.js     # เก็บภาพไว้ดูเอง
 */
let chromium;
try {
  ({ chromium } = require('playwright'));
} catch (e) {
  console.error('ข้ามการตรวจเลย์เอาต์: ยังไม่ได้ลง Playwright\n' +
                '  npm install playwright --no-save && npx playwright install chromium');
  process.exit(0);
}
const path = require('path');
const fs = require('fs');
const FILE = 'file://' + path.resolve(__dirname, '..', 'index.html');
const OUT = process.env.SHOT_DIR || path.join(require('os').tmpdir(), 'thai-exam-ai-socratic-tutor-shots') + path.sep;
fs.mkdirSync(OUT, { recursive: true });

const DEVICES = [
  { name: 'iPhone SE',        w: 375,  h: 667,  dsr: 2 },
  { name: 'iPhone 12/13',     w: 390,  h: 844,  dsr: 3 },
  { name: 'iPhone 15 Pro Max',w: 430,  h: 932,  dsr: 3 },
  { name: 'Galaxy S8',        w: 360,  h: 740,  dsr: 3 },
  { name: 'iPad mini แนวตั้ง', w: 768,  h: 1024, dsr: 2 },
  { name: 'iPad Pro แนวนอน',   w: 1024, h: 768,  dsr: 2 },
  { name: 'โน้ตบุ๊ก',          w: 1280, h: 800,  dsr: 1 },
  { name: 'เดสก์ท็อป',         w: 1920, h: 1080, dsr: 1 },
];

const rows = [];
const fail = [];
const note = (dev, k, ok, detail) => {
  if (!ok) fail.push(`${dev} — ${k}: ${detail}`);
};

(async () => {
  // ใช้ chromium ที่ Playwright หาเจอเอง ถ้าไม่มีค่อยใช้ตัวที่ตั้งไว้ใน PW_CHROMIUM
  const exe = process.env.PW_CHROMIUM
    || (fs.existsSync('/opt/pw-browsers/chromium-1194/chrome-linux/chrome')
        ? '/opt/pw-browsers/chromium-1194/chrome-linux/chrome' : undefined);
  const b = await chromium.launch(exe ? { executablePath: exe } : {});
  const errs = [];

  for (const d of DEVICES) {
    const p = await b.newPage({ viewport: { width: d.w, height: d.h }, deviceScaleFactor: d.dsr,
                                isMobile: d.w < 900, hasTouch: d.w < 900 });
    p.on('pageerror', e => errs.push(`${d.name}: ${e.message}`));
    await p.goto(FILE);
    await p.waitForSelector('#courseGrid .course-card');

    // ---- หน้าแรก ----
    const home = await p.evaluate(() => ({
      doc: document.documentElement.scrollWidth,
      win: window.innerWidth,
      cards: document.querySelectorAll('.course-card').length,
      cols: new Set([...document.querySelectorAll('.course-card')]
              .map(c => Math.round(c.getBoundingClientRect().left))).size,
      hdr: Math.round(document.querySelector('header').getBoundingClientRect().height),
      // ข้อความใดถูกตัดหายในแนวนอนบ้าง
      clipped: [...document.querySelectorAll('.c-count, .c-units button .u-t, .r-main')]
        .filter(e => e.scrollWidth > e.clientWidth + 1).length,
    }));
    note(d.name, 'หน้าแรกไม่ล้นแนวนอน', home.doc <= home.win, `${home.doc} > ${home.win}`);
    if (d.w <= 430) await p.screenshot({ path: `${OUT}${d.w}-home.png` });

    // ---- หน้าข้อสอบ: เข้าคณิต ม.3 (การ์ดที่หน่วยเยอะสุด) ----
    await p.evaluate(() => {
      const names = [...document.querySelectorAll('#courseGrid .c-name')];
      const i = names.findIndex(n => n.textContent.includes('ม.3'));
      document.querySelectorAll('#courseGrid .c-go')[i].click();
    });
    await p.waitForSelector('#examCard');
    const exam = await p.evaluate(() => ({
      doc: document.documentElement.scrollWidth,
      win: window.innerWidth,
      hdr: Math.round(document.querySelector('header').getBoundingClientRect().height),
      vh: window.innerHeight,
      card: Math.round(document.querySelector('#examCard').getBoundingClientRect().width),
      burger: getComputedStyle(document.querySelector('#navToggle')).display !== 'none'
              && !document.querySelector('#navToggle').classList.contains('hide'),
      hh: parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--hh')),
    }));
    note(d.name, 'หน้าข้อสอบไม่ล้นแนวนอน', exam.doc <= exam.win, `${exam.doc} > ${exam.win}`);
    note(d.name, '--hh ตรงกับหัวเรื่องจริง', Math.abs(exam.hh - exam.hdr) < 2, `${exam.hh} vs ${exam.hdr}`);
    note(d.name, 'ปุ่ม ☰ โผล่เฉพาะจอแคบ', exam.burger === (d.w <= 760), `burger=${exam.burger}`);

    // ---- เมนู ☰ (เฉพาะจอแคบ) ----
    let menuOK = '—';
    if (d.w <= 760) {
      await p.click('#navToggle');
      const m = await p.evaluate(() => {
        const ids = ['homeBtn','filterToggle','overviewBtn','aiSetupBtn','printExamBtn','printAnswerBtn'];
        return {
          shown: ids.filter(i => document.getElementById(i).getBoundingClientRect().height > 0).length,
          doc: document.documentElement.scrollWidth, win: window.innerWidth,
          hh: parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--hh')),
          hdr: Math.round(document.querySelector('header').getBoundingClientRect().height),
          // ปุ่มต้องกดโดนบนมือถือ (แนะนำ >= 40px)
          minH: Math.min(...ids.map(i => Math.round(document.getElementById(i).getBoundingClientRect().height))),
        };
      });
      note(d.name, 'เมนูครบ 6 ปุ่ม', m.shown === 6, `${m.shown}`);
      note(d.name, 'กางเมนูแล้วไม่ล้นแนวนอน', m.doc <= m.win, `${m.doc} > ${m.win}`);
      note(d.name, '--hh อัปเดตตอนกางเมนู', Math.abs(m.hh - m.hdr) < 2, `${m.hh} vs ${m.hdr}`);
      note(d.name, 'ปุ่มในเมนูสูงพอกดโดน (>=40px)', m.minH >= 40, `${m.minH}px`);
      menuOK = `${m.shown} ปุ่ม · สูง ${m.minH}px`;
      if (d.w === 390) await p.screenshot({ path: `${OUT}390-menu.png` });
      await p.keyboard.press('Escape');
    }

    // ---- แผงตัวกรอง ---- (จอแคบ ปุ่มนี้อยู่ในเมนู ☰ ต้องกางเมนูก่อน)
    const openMenu = async () => { if (d.w <= 760) await p.click('#navToggle'); };
    await openMenu();
    await p.click('#filterToggle');
    await p.waitForTimeout(200);
    const filt = await p.evaluate(() => ({
      doc: document.documentElement.scrollWidth, win: window.innerWidth,
      sbW: Math.round(document.querySelector('#sidebar').getBoundingClientRect().width),
      cardW: Math.round(document.querySelector('#examCard').getBoundingClientRect().width),
    }));
    note(d.name, 'กางตัวกรองแล้วไม่ล้นแนวนอน', filt.doc <= filt.win, `${filt.doc} > ${filt.win}`);
    note(d.name, 'กางตัวกรองแล้วการ์ดยังกว้างพอ', filt.cardW >= 280, `${filt.cardW}px`);
    if (d.w === 390) await p.screenshot({ path: `${OUT}390-filter.png` });
    await openMenu();
    await p.click('#filterToggle');

    // ---- แผงพี่หลวง ----
    await p.evaluate(() => localStorage.setItem('funnymath-ai-v1',
      JSON.stringify({ key: 'sk-ant-test', model: 'claude-opus-5' })));
    await p.reload();
    // รีโหลดแล้วกลับมาหน้าแรกเสมอ ต้องกดเข้าหน้าข้อสอบใหม่
    await p.waitForSelector('#courseGrid .course-card');
    await p.evaluate(() => {
      const names = [...document.querySelectorAll('#courseGrid .c-name')];
      const i = names.findIndex(n => n.textContent.includes('ม.3'));
      document.querySelectorAll('#courseGrid .c-go')[i].click();
    });
    await p.waitForSelector('#examCard', { state: 'visible' });
    await p.click('#tutorToggle');
    await p.waitForSelector('#tutorPanel.show');
    // แผงเลื่อนเข้าด้วย transform .22s — ถ้าวัดทันทีจะได้ตำแหน่งตอนยังอยู่นอกจอ
    await p.evaluate(() => new Promise(res => {
      const el = document.querySelector('#tutorPanel');
      const done = () => { el.removeEventListener('transitionend', done); requestAnimationFrame(res); };
      el.addEventListener('transitionend', done);
      setTimeout(res, 1200);
    }));
    const tut = await p.evaluate(() => {
      const t = document.querySelector('#tutorPanel').getBoundingClientRect();
      const c = document.querySelector('#examCard').getBoundingClientRect();
      return { doc: document.documentElement.scrollWidth, win: window.innerWidth,
               top: Math.round(t.top), hdr: Math.round(document.querySelector('header').getBoundingClientRect().height),
               panelW: Math.round(t.width), cardW: Math.round(c.width),
               overlap: Math.round(c.right - t.left),
               closeIn: (() => { const x = document.querySelector('#tutorClose').getBoundingClientRect();
                                 return x.left >= -1 && x.right <= window.innerWidth + 1; })() };
    });
    note(d.name, 'กางพี่หลวงแล้วไม่ล้นแนวนอน', tut.doc <= tut.win, `${tut.doc} > ${tut.win}`);
    note(d.name, 'แผงพี่หลวงเริ่มใต้หัวเรื่องพอดี', Math.abs(tut.top - tut.hdr) < 2, `${tut.top} vs ${tut.hdr}`);
    if (d.w <= 1100) note(d.name, 'จอแคบ: แผงกางเต็มความกว้าง', tut.panelW === tut.win, `${tut.panelW}/${tut.win}`);
    note(d.name, 'ปุ่ม ✕ ของแผงอยู่ในจอ', tut.closeIn, 'ปุ่มปิดหลุดออกนอกจอ');
    if (d.w > 1100) note(d.name, 'จอกว้าง: แผงไม่ทับการ์ดข้อสอบ', tut.overlap <= 1, `ทับ ${tut.overlap}px`);
    if (d.w === 390 || d.w === 1920) await p.screenshot({ path: `${OUT}${d.w}-tutor.png` });

    rows.push([d.name, `${d.w}×${d.h}`, home.doc <= home.win ? 'ไม่ล้น' : `ล้น ${home.doc-home.win}px`,
               `${home.cols} คอลัมน์`, `${exam.hdr}px (${Math.round(exam.hdr/exam.vh*100)}%)`,
               `${exam.card}px`, menuOK, `${tut.panelW}px`]);
    await p.close();
  }

  const hdr = ['อุปกรณ์','ขนาดจอ','หน้าแรก','การ์ดวิชา','หัวเรื่อง','การ์ดข้อสอบ','เมนู ☰','แผงพี่หลวง'];
  const w = hdr.map((h,i) => Math.max(h.length, ...rows.map(r => String(r[i]).length)));
  const line = r => '  ' + r.map((c,i) => String(c).padEnd(w[i])).join(' │ ');
  console.log(line(hdr));
  console.log('  ' + w.map(n => '─'.repeat(n)).join('─┼─'));
  rows.forEach(r => console.log(line(r)));
  console.log('\n' + (fail.length ? `✘ ไม่ผ่าน ${fail.length} ข้อ:\n  ` + fail.join('\n  ')
                                  : `✔ ผ่านทุกข้อ (${DEVICES.length} อุปกรณ์ × 10 เช็ก)`));
  console.log('page errors:', errs.length ? errs : 'none');
  await b.close();
})();
