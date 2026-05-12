"""
보령국민체육센터 공공데이터 → SQLite DB 구축 스크립트
- 3개 CSV(입장기록, 강습이력, 강좌신청정보)를 클린징 후 SQLite에 적재
"""
import pandas as pd
import sqlite3
from pathlib import Path

DB_PATH = Path("bcsports.db")
if DB_PATH.exists():
    DB_PATH.unlink()

conn = sqlite3.connect(DB_PATH)

# ============================================================
# 1. 입장기록 (entries)
# ============================================================
print("[1/3] 입장기록 클린징 중...")
entries = pd.read_csv("입장기록.csv", encoding="cp949", low_memory=False)

# 공백 제거
entries["성별"] = entries["성별"].str.strip()
entries["센터명"] = entries["센터명"].str.strip()

# 입장시간(int) → HH:MM 문자열, 시(hour) 분리
entries["입장시간_str"] = entries["입장시간"].astype(str).str.zfill(4)
entries["입장시"] = entries["입장시간_str"].str[:2].astype(int)
entries["입장분"] = entries["입장시간_str"].str[2:].astype(int)

# 비정상 시간 제거 (24시 이상, 60분 이상)
entries = entries[(entries["입장시"] < 24) & (entries["입장분"] < 60)].copy()

# 입장일자 datetime 변환, 잘못된 날짜 제거
entries["입장일자"] = pd.to_datetime(entries["입장일자"], errors="coerce")
entries = entries.dropna(subset=["입장일자"])

# 파생변수: 연, 월, 요일(0=월), 연월
entries["연도"] = entries["입장일자"].dt.year
entries["월"] = entries["입장일자"].dt.month
entries["요일"] = entries["입장일자"].dt.dayofweek
entries["연월"] = entries["입장일자"].dt.strftime("%Y-%m")

# 회원번호 0 = 익명/비회원 플래그
entries["회원여부"] = (entries["회원번호"] != 0).astype(int)

# 체류시간 계산 (퇴장 정보 있을 때만)
entries["퇴장일자_dt"] = pd.to_datetime(entries["퇴장일자"], errors="coerce")
mask = entries["퇴장일자_dt"].notna() & entries["퇴장시간"].notna()
entries["퇴장시간_str"] = ""
entries.loc[mask, "퇴장시간_str"] = entries.loc[mask, "퇴장시간"].astype(int).astype(str).str.zfill(4)

def compute_stay(row):
    if pd.isna(row["퇴장일자_dt"]) or row["퇴장시간_str"] == "":
        return None
    try:
        ent = row["입장일자"] + pd.Timedelta(hours=row["입장시"], minutes=row["입장분"])
        ext_h = int(row["퇴장시간_str"][:2])
        ext_m = int(row["퇴장시간_str"][2:])
        if ext_h >= 24 or ext_m >= 60:
            return None
        ext = row["퇴장일자_dt"] + pd.Timedelta(hours=ext_h, minutes=ext_m)
        diff = (ext - ent).total_seconds() / 60
        if 0 < diff < 24*60:  # 0~24시간 사이만 유효
            return diff
        return None
    except Exception:
        return None

entries["체류시간_분"] = entries.apply(compute_stay, axis=1)

# 최종 컬럼 선택
entries_clean = entries[[
    "센터명", "회원번호", "회원여부", "성별",
    "입장일자", "입장시", "입장분",
    "연도", "월", "요일", "연월",
    "체류시간_분"
]].rename(columns={
    "센터명": "center_name",
    "회원번호": "member_id",
    "회원여부": "is_member",
    "성별": "gender",
    "입장일자": "entry_date",
    "입장시": "entry_hour",
    "입장분": "entry_minute",
    "연도": "year",
    "월": "month",
    "요일": "dow",
    "연월": "ym",
    "체류시간_분": "stay_minutes",
})
entries_clean["entry_date"] = entries_clean["entry_date"].dt.strftime("%Y-%m-%d")
entries_clean.to_sql("entries", conn, index=False)
print(f"  → entries 테이블 {len(entries_clean):,}행 적재")

# ============================================================
# 2. 강습이력 (lessons)
# ============================================================
print("[2/3] 강습이력 클린징 중...")
lessons = pd.read_csv("강습이력.csv", encoding="cp949", low_memory=False)
lessons.columns = [c.strip() for c in lessons.columns]
lessons["강습방법"] = lessons["강습방법"].str.strip()
lessons["센터명"] = lessons["센터명"].str.strip()

# 잘못된 날짜 제거
lessons["강습시작일자"] = pd.to_datetime(lessons["강습시작일자"], errors="coerce")
lessons["강습종료일자"] = pd.to_datetime(lessons["강습종료일자"], errors="coerce")
lessons["등록일시"] = pd.to_datetime(lessons["등록일시"], errors="coerce")
lessons = lessons.dropna(subset=["강습시작일자"])

lessons["연도"] = lessons["강습시작일자"].dt.year
lessons["연월"] = lessons["강습시작일자"].dt.strftime("%Y-%m")
lessons["강습기간_일"] = (lessons["강습종료일자"] - lessons["강습시작일자"]).dt.days

lessons_clean = lessons.rename(columns={
    "센터명": "center_name",
    "회원번호": "member_id",
    "강습시작일자": "lesson_start",
    "강습종료일자": "lesson_end",
    "강습방법": "method",
    "등록일시": "registered_at",
    "연도": "year",
    "연월": "ym",
    "강습기간_일": "duration_days",
})[["center_name", "member_id", "lesson_start", "lesson_end", "method",
    "registered_at", "year", "ym", "duration_days"]]

for col in ["lesson_start", "lesson_end"]:
    lessons_clean[col] = lessons_clean[col].dt.strftime("%Y-%m-%d")
lessons_clean["registered_at"] = lessons_clean["registered_at"].dt.strftime("%Y-%m-%d %H:%M")
lessons_clean.to_sql("lessons", conn, index=False)
print(f"  → lessons 테이블 {len(lessons_clean):,}행 적재")

# ============================================================
# 3. 강좌신청정보 (applications)
# ============================================================
print("[3/3] 강좌신청정보 클린징 중...")
apps = pd.read_csv("강좌신청정보.csv", encoding="cp949", low_memory=False)
apps["센터명"] = apps["센터명"].str.strip()

apps["접수일자"] = pd.to_datetime(apps["접수일자"], errors="coerce")
apps["강습시작일자"] = pd.to_datetime(apps["강습시작일자"], errors="coerce")
apps["강습종료일자"] = pd.to_datetime(apps["강습종료일자"], errors="coerce")
apps = apps.dropna(subset=["접수일자"])

# 강습시작시간(int 610 = 06:10) → hour
apps["시작시각_str"] = apps["강습시작시간"].astype(str).str.zfill(4)
apps["시작시"] = apps["시작시각_str"].str[:2].astype(int)
apps = apps[apps["시작시"] < 24].copy()

apps["연도"] = apps["접수일자"].dt.year
apps["연월"] = apps["접수일자"].dt.strftime("%Y-%m")
apps["할인율"] = 0.0
nonzero = apps["강습비용"] > 0
apps.loc[nonzero, "할인율"] = (apps.loc[nonzero, "할인금액"] / apps.loc[nonzero, "강습비용"]) * 100
apps["유료여부"] = (apps["강습비용"] > 0).astype(int)

apps_clean = apps.rename(columns={
    "센터명": "center_name",
    "강좌신청접수번호": "application_no",
    "접수일자": "applied_date",
    "강습시작일자": "lesson_start",
    "강습종료일자": "lesson_end",
    "시작시": "start_hour",
    "강습비용": "price",
    "할인금액": "discount",
    "결제금액": "paid",
    "할인율": "discount_rate",
    "유료여부": "is_paid",
    "연도": "year",
    "연월": "ym",
})[["center_name", "application_no", "applied_date", "lesson_start", "lesson_end",
    "start_hour", "price", "discount", "paid", "discount_rate", "is_paid",
    "year", "ym"]]

for col in ["applied_date", "lesson_start", "lesson_end"]:
    apps_clean[col] = apps_clean[col].dt.strftime("%Y-%m-%d")
apps_clean.to_sql("applications", conn, index=False)
print(f"  → applications 테이블 {len(apps_clean):,}행 적재")

# 인덱스
print("\n인덱스 생성 중...")
cur = conn.cursor()
cur.executescript("""
CREATE INDEX idx_entries_date ON entries(entry_date);
CREATE INDEX idx_entries_ym ON entries(ym);
CREATE INDEX idx_entries_member ON entries(member_id);
CREATE INDEX idx_lessons_start ON lessons(lesson_start);
CREATE INDEX idx_lessons_method ON lessons(method);
CREATE INDEX idx_lessons_member ON lessons(member_id);
CREATE INDEX idx_apps_year ON applications(year);
""")
conn.commit()

# 요약
print("\n=== DB 구축 완료 ===")
for tbl in ["entries", "lessons", "applications"]:
    cnt = cur.execute(f"SELECT COUNT(*) FROM {tbl}").fetchone()[0]
    print(f"  {tbl}: {cnt:,}행")

conn.close()
print(f"\nSaved to {DB_PATH.resolve()}")
