#!/usr/bin/env bash
# บอกว่า GitHub Pages เสิร์ฟของตรงกับ main แล้วหรือยัง
#
# ตอบคำถามที่แท็บ Actions ตอบไม่ได้: "build ผ่าน" ไม่ได้แปลว่า "ผู้เรียนเห็นของใหม่แล้ว"
# เพราะหน้าเว็บส่ง cache-control: max-age=600 — ขอบ CDN และเบราว์เซอร์ยังคืนของเดิม
# ได้อีกถึง 10 นาทีหลัง deploy สำเร็จ สคริปต์นี้จึงเทียบ "ไฟล์จริงที่เสิร์ฟอยู่"
# กับ "ไฟล์ที่ main ชี้อยู่" ทีละไบต์ ไม่ได้ดูสถานะ build
#
# **เทียบไฟล์ที่ push ล่าสุดแก้จริง** ไม่ใช่แค่ index.html — ถ้าเทียบเฉพาะ index.html
# แล้ว push นั้นไม่ได้แตะ index.html (เช่นแก้แต่เอกสารหรือสคริปต์) จะได้เครื่องหมายถูก
# ทันทีตั้งแต่ยังไม่ deploy ซึ่งเป็นคำตอบที่ผ่านโดยไม่มีหลักฐาน
#
# ไม่ต้องใช้โทเคน — อ่านจากเว็บสาธารณะกับ git remote เท่านั้น
#
# รัน:  bash tools/pages_status.sh            เทียบไฟล์ที่ push ล่าสุดแก้ + index.html
#       bash tools/pages_status.sh --all      เทียบไฟล์ข้อมูลรายวิชาทุกไฟล์ด้วย
#       bash tools/pages_status.sh --watch    วนเช็กจนตรง (สูงสุด 10 นาที)
#
# รหัสออก 0 = ตรงกับ main แล้ว · 1 = ยังไม่ตรง · 2 = เรียกใช้ผิดหรือเข้าเว็บไม่ได้
set -uo pipefail

cd "$(dirname "$0")/.."

ALL=0
WATCH=0
MAXFILES=25          # push ที่แก้เป็นร้อยไฟล์มีจริง — ตัดจำนวน แต่บอกว่าตัดไปเท่าไร
for a in "$@"; do
  case "$a" in
    --all) ALL=1 ;;
    --watch) WATCH=1 ;;
    # พิมพ์บล็อกคอมเมนต์หัวไฟล์จนกว่าจะหมด — ไม่ผูกกับเลขบรรทัด ซึ่งเลื่อนทุกครั้งที่แก้
    -h|--help) awk 'NR>1 && /^#/ {sub(/^# ?/, ""); print; next} NR>1 {exit}' "$0"; exit 0 ;;
    *) echo "ไม่รู้จักตัวเลือก '$a' — ดู --help"; exit 2 ;;
  esac
done

# ---- หา URL ของเว็บจาก remote — ไม่ฮาร์ดโค้ดชื่อ repo ----
REMOTE=$(git remote get-url origin 2>/dev/null) || { echo "ไม่มี remote ชื่อ origin"; exit 2; }
SLUG=$(printf '%s' "$REMOTE" | sed -E 's#^git@github\.com:#https://github.com/#' \
                               | sed -E 's#^https://[^/]+/##; s#\.git$##')
OWNER=${SLUG%%/*}
REPO=${SLUG##*/}
[ -n "$OWNER" ] && [ -n "$REPO" ] || { echo "อ่าน owner/repo จาก '$REMOTE' ไม่ได้"; exit 2; }
SITE="https://${OWNER}.github.io/${REPO}"

fetch() { curl -fsS -H 'Cache-Control: no-cache' -H 'Pragma: no-cache' "$1"; }
sha() { sha256sum | cut -c1-12; }

check_once() {
  # ต้องรู้ว่า main ชี้ที่ commit ไหน "ตอนนี้" ไม่ใช่ตอน fetch ครั้งก่อน
  git fetch -q origin main 2>/dev/null || { echo "fetch origin main ไม่สำเร็จ"; return 2; }
  local head short files=() f live want stale=0
  head=$(git rev-parse origin/main)
  short=${head:0:7}

  # ไฟล์ที่ push ล่าสุดแก้ = สิ่งที่ต้องกลายเป็นของใหม่บนเว็บพอดี
  # ใช้ ^1 เพื่อให้ merge commit เทียบกับยอด main เดิม ไม่ใช่กับปลายแบรนช์ที่ถูก merge เข้ามา
  files=()
  if git rev-parse -q --verify "$head^1" >/dev/null; then
    while read -r f; do [ -n "$f" ] && files+=("$f"); done < <(
      git diff --name-only "$head^1" "$head")
  fi
  if [ "${#files[@]}" -gt "$MAXFILES" ]; then
    echo "  (push ล่าสุดแก้ ${#files[@]} ไฟล์ — เทียบแค่ $MAXFILES ไฟล์แรก)"
    files=("${files[@]:0:$MAXFILES}")
  fi
  # index.html เป็นหน้าที่ผู้เรียนเปิดจริง เทียบไว้เสมอแม้ push ล่าสุดจะไม่ได้แตะ
  case " ${files[*]-} " in *" index.html "*) ;; *) files+=("index.html") ;; esac

  if [ "$ALL" = 1 ]; then
    # อ่านรายชื่อไฟล์ข้อมูลจาก MANIFEST ของ main — เพิ่มวิชาแล้วไม่ต้องมาแก้สคริปต์
    while read -r f; do files+=("data/${f}.json"); done < <(
      git show "origin/main:index.html" |
      grep -o '"slug": "[a-z0-9-]*"' | sed 's/.*"\([a-z0-9-]*\)"$/\1/' | sort -u)
  fi

  local w=0
  for f in "${files[@]}"; do [ "${#f}" -gt "$w" ] && w=${#f}; done
  for f in "${files[@]}"; do
    live=$(fetch "$SITE/$f" 2>/dev/null | sha)
    if ! git cat-file -e "origin/main:$f" 2>/dev/null; then
      # ไฟล์ถูกลบใน push นี้ — deploy สำเร็จแปลว่าเว็บต้องไม่มีไฟล์นี้แล้ว
      if [ -z "$live" ]; then
        printf '  %-*s ✔ ถูกลบออกจากเว็บแล้ว\n' "$w" "$f"
      else
        printf '  %-*s ✘ ลบใน main แล้วแต่เว็บยังเสิร์ฟอยู่\n' "$w" "$f"
        stale=1
      fi
      continue
    fi
    want=$(git show "origin/main:$f" | sha)
    if [ -z "$live" ]; then
      printf '  %-*s ✘ ดึงจากเว็บไม่ได้\n' "$w" "$f"
      stale=1
    elif [ "$want" = "$live" ]; then
      printf '  %-*s ✔ ตรงกับ main\n' "$w" "$f"
    else
      printf '  %-*s ✘ ยังเป็นของเดิม (main %s · เว็บ %s)\n' "$w" "$f" "$want" "$live"
      stale=1
    fi
  done

  # เวลาที่ deploy กับอายุที่ค้างอยู่ในแคช — บอกว่าที่เห็นเป็นของสดหรือของค้าง
  local hdr lastmod age
  hdr=$(curl -fsSI "$SITE/index.html" 2>/dev/null)
  lastmod=$(printf '%s' "$hdr" | tr -d '\r' | sed -n 's/^last-modified: //Ip')
  age=$(printf '%s' "$hdr" | tr -d '\r' | sed -n 's/^age: //Ip')
  echo "  ─────"
  echo "  main อยู่ที่   $short"
  [ -n "$lastmod" ] && echo "  เว็บอัปเดต    $lastmod"
  [ -n "$age" ] && echo "  อายุในแคช     ${age} วินาที (สูงสุด 600)"
  return $stale
}

echo "เว็บ: $SITE"
if [ "$WATCH" = 0 ]; then
  check_once
  rc=$?
  echo
  case $rc in
    0) echo "✅ Pages เสิร์ฟของตรงกับ main แล้ว" ;;
    1) echo "⏳ ยังไม่ตรง — build ใช้เวลาราว 30 วินาที และแคชอาจค้างได้ถึง 10 นาที"
       echo "   วนเช็กให้อัตโนมัติ: bash tools/pages_status.sh --watch" ;;
  esac
  exit $rc
fi

# --watch: เช็กทุก 15 วินาที ไม่เกิน 10 นาที ซึ่งครอบทั้งเวลา build และอายุแคชเต็มที่
DEADLINE=$((SECONDS + 600))
n=0
while :; do
  n=$((n + 1))
  echo "── ครั้งที่ $n ($(date '+%H:%M:%S')) ──"
  if check_once; then
    echo
    echo "✅ Pages เสิร์ฟของตรงกับ main แล้ว"
    exit 0
  fi
  if [ "$SECONDS" -ge "$DEADLINE" ]; then
    echo
    echo "⏰ ครบ 10 นาทีแล้วยังไม่ตรง — เปิดแท็บ Actions ดู workflow"
    echo "   'pages build and deployment' ว่าล้มหรือยังไม่ได้เริ่ม"
    exit 1
  fi
  sleep 15
done
