#!/usr/bin/env bash
# ชุดตรวจทั้งหมดของ repo นี้ — รันในเครื่อง ไม่ต้องพึ่ง GitHub Actions runner
#
#   bash tools/check.sh              ตรวจทั้งหมด
#   bash tools/check.sh --install    ตั้ง git hook ให้ตรวจอัตโนมัติก่อน push
#
# ตั้งใจให้เหมือนกับที่ workflow เคยรันทุกขั้น เพื่อให้ผลตรงกัน
set -uo pipefail
cd "$(dirname "$0")/.."

BOLD=$'\033[1m'; RED=$'\033[31m'; GREEN=$'\033[32m'; DIM=$'\033[2m'; OFF=$'\033[0m'
[ -t 1 ] || { BOLD=''; RED=''; GREEN=''; DIM=''; OFF=''; }

if [ "${1-}" = "--install" ]; then
  git config core.hooksPath .githooks || exit 1
  echo "${GREEN}✔${OFF} ตั้ง core.hooksPath = .githooks แล้ว — ต่อไป git push จะตรวจให้ก่อนอัตโนมัติ"
  echo "${DIM}  ยกเลิกด้วย: git config --unset core.hooksPath${OFF}"
  exit 0
fi

fails=0
step() {                                  # step "ชื่อขั้น" คำสั่ง...
  local name="$1"; shift
  printf '%s▶ %s%s\n' "$BOLD" "$name" "$OFF"
  local out
  if out=$("$@" 2>&1); then
    printf '%s  ✔ ผ่าน%s\n' "$GREEN" "$OFF"
    [ -n "$out" ] && printf '%s%s%s\n' "$DIM" "$(printf '%s' "$out" | tail -3)" "$OFF"
  else
    printf '%s  ✘ ไม่ผ่าน%s\n%s\n' "$RED" "$OFF" "$out"
    fails=$((fails + 1))
  fi
}

need() { command -v "$1" >/dev/null 2>&1 || { printf '%s✘ ไม่พบคำสั่ง %s%s\n' "$RED" "$1" "$OFF"; exit 2; }; }
need python3
need node

# 1. คลังรูปต้องตรงกับสคริปต์ที่สร้างมัน (ไม่งั้นรูปในหน้าเว็บกับซอร์สจะคนละเวอร์ชัน)
figures_fresh() {
  python3 tools/build_figures.py >/dev/null || return 1
  git diff --exit-code -- questions/figures.json >/dev/null \
    || { echo "questions/figures.json ไม่ตรงกับ tools/build_figures.py — รันสคริปต์แล้ว commit ใหม่"; return 1; }
}
step "คลังรูปตรงกับ tools/build_figures.py" figures_fresh

# 2. index.html ต้องประกอบจากคลังข้อสอบแล้วตรงกัน
step "index.html ตรงกับคลังข้อสอบ" python3 tools/build.py --check

# 3. schema, เฉลย, SVG, syntax, สำเนาชื่อไทย
step "คลังข้อสอบและหน้าเว็บ (validate.py)" python3 tools/validate.py

# 4. พฤติกรรมหน้าเว็บใน jsdom
dom_test() {
  node -e "require.resolve('jsdom')" 2>/dev/null \
    || npm install jsdom --no-save --silent >/dev/null 2>&1 \
    || { echo "ติดตั้ง jsdom ไม่สำเร็จ — ต้องต่อเน็ตครั้งแรกครั้งเดียว"; return 1; }
  node tools/dom_test.cjs
}
step "พฤติกรรมหน้าเว็บ (dom_test.cjs)" dom_test

echo
if [ "$fails" -eq 0 ]; then
  printf '%s%s✔ ผ่านทุกขั้น%s\n' "$BOLD" "$GREEN" "$OFF"
else
  printf '%s%s✘ ไม่ผ่าน %d ขั้น%s\n' "$BOLD" "$RED" "$fails" "$OFF"
fi
exit $(( fails > 0 ))
