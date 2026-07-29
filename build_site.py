#!/usr/bin/env python3.11
# -*- coding: utf-8 -*-
"""读取 archive.json，计算日/周/月环比，生成可日期查询的单文件 HTML 网站。"""
import json, os
from datetime import datetime, timedelta
from urllib.parse import quote

ARCHIVE = "archive.json"
OUT = "广州新房网签数据.html"

def load_archive():
    with open(ARCHIVE, "r", encoding="utf-8") as f:
        return json.load(f)

def compute_comparisons(archive):
    dates = sorted(archive.get("records", {}).keys())
    records = archive["records"]
    projects = list(next(iter(records.values())).keys()) if records else []
    out = {"dates": dates, "meta": archive.get("meta", {}), "projects": projects, "records": {}}
    for date in dates:
        d = datetime.strptime(date, "%Y-%m-%d")
        out["records"][date] = {}
        for proj in projects:
            snap = records[date].get(proj, {"buildings": [], "summary": {}})
            # reference dates
            prev = _prev_date(date, dates)
            wstart = _week_start(date, dates)
            mstart = _month_start(date, dates)
            # building level
            bld_out = []
            for b in snap.get("buildings", []):
                bld_out.append(_attach_compare(b, date, prev, wstart, mstart, records, proj))
            # summary level
            summary = snap.get("summary", {}).copy()
            summary = _attach_compare(summary, date, prev, wstart, mstart, records, proj, is_summary=True)
            summary["count"] = len(bld_out)
            out["records"][date][proj] = {"buildings": bld_out, "summary": summary}
    return out

def _prev_date(date, dates):
    idx = dates.index(date)
    return dates[idx-1] if idx > 0 else None

def _week_start(date, dates):
    """返回上周同日（same weekday, previous week）的存档日期。
    若恰好不存在，回退到上周最接近的日期。
    若无上周数据则返回 None。"""
    d = datetime.strptime(date, "%Y-%m-%d")
    target = d - timedelta(days=7)  # 上周同日
    # 优先精确匹配上周同日
    exact = [dd for dd in dates if dd == target.strftime("%Y-%m-%d")]
    if exact:
        return exact[0]
    # 回退：上周（周一到周日）区间内最接近的日期
    week_mon = target - timedelta(days=target.weekday())
    week_sun = week_mon + timedelta(days=6)
    candidates = [dd for dd in dates if week_mon <= datetime.strptime(dd, "%Y-%m-%d") <= week_sun]
    if candidates:
        return candidates[-1]  # 取最近的
    # 更早的数据
    before = [dd for dd in dates if datetime.strptime(dd, "%Y-%m-%d") < week_mon]
    return before[-1] if before else None

def _month_start(date, dates):
    """返回上月同日的存档日期。
    若上月同日不存在（如 3/31 对应 2/31 不存在），回退到上月最后一天。
    若无上月数据则返回 None。"""
    d = datetime.strptime(date, "%Y-%m-%d")
    # 计算上月同日
    if d.month == 1:
        target_month, target_year = 12, d.year - 1
    else:
        target_month, target_year = d.month - 1, d.year
    # 处理月末溢出（如 3/31 → 2/28）
    target_day = min(d.day, 28)
    while True:
        try:
            target = datetime(target_year, target_month, target_day)
            break
        except ValueError:
            target_day -= 1
    # 精确匹配
    exact = [dd for dd in dates if dd == target.strftime("%Y-%m-%d")]
    if exact:
        return exact[0]
    # 回退：上月范围内最接近的日期
    month_start_d = target.replace(day=1)
    if target.month == 12:
        month_end_d = target.replace(year=target.year+1, month=1, day=1) - timedelta(days=1)
    else:
        month_end_d = target.replace(month=target.month+1, day=1) - timedelta(days=1)
    candidates = [dd for dd in dates if month_start_d <= datetime.strptime(dd, "%Y-%m-%d") <= month_end_d]
    if candidates:
        return candidates[-1]
    # 更早的数据
    before = [dd for dd in dates if datetime.strptime(dd, "%Y-%m-%d") < month_start_d]
    return before[-1] if before else None

def _attach_compare(item, date, prev, wstart, mstart, records, proj, is_summary=False):
    out = dict(item)
    curr = item.get("signed", 0) or 0
    for label, ref_date in [("day", prev), ("week", wstart), ("month", mstart)]:
        if ref_date and ref_date != date and ref_date in records and proj in records[ref_date]:
            ref_rec = records[ref_date][proj]
            if is_summary:
                ref = ref_rec.get("summary", {})
            else:
                ref = next((x for x in ref_rec.get("buildings", []) if x.get("name") == item.get("name")), None)
            if ref is None:
                out[f"{label}_delta"] = None
                out[f"{label}_pct"] = None
                continue
            ref_val = ref.get("signed", 0) or 0
            delta = curr - ref_val
            pct = (delta / ref_val) if ref_val > 0 else None
            out[f"{label}_delta"] = delta
            out[f"{label}_pct"] = round(pct, 6) if pct is not None else None
        else:
            out[f"{label}_delta"] = None
            out[f"{label}_pct"] = None
    return out

def pct_html(v):
    if v is None:
        return "<span class=\"na\">—</span>"
    cls = "up" if v > 0 else ("down" if v < 0 else "zero")
    return f'<span class="{cls}">{v*100:+.2f}%</span>'

def num_html(v):
    if v is None:
        return "<span class=\"na\">—</span>"
    sign = "+" if v > 0 else ""
    return f'<span class="num">{sign}{v:,}</span>'

def rate_html(v):
    if v is None:
        return "<span class=\"na\">—</span>"
    return f'<span class="rate">{v*100:.2f}%</span>'

def build_html(data):
    dates = data["dates"]
    latest = dates[-1] if dates else ""
    data_json = json.dumps(data, ensure_ascii=False, indent=2)
    data_json = data_json.replace("</", "<\\/")  # avoid </script> injection
    # mapping notes
    mapping_notes = {
        "珑曜上城": "官方备案名：珑曜花园",
        "星汇锦城": "官方备案名：明颂花园 + 盛颂花园（越秀·大学·星汇锦城）",
        "繁花里": "官方备案名：繁花院",
        "檐屿城": "官方备案名：檐屿花园",
        "亚运城环宇熙和": "阳光家缘未以“熙和/环宇熙和”备案；本表以最新在售官方组团“亚运城B地块B-6~B-9幢住宅（预售证20260088）”代理"
    }

    project_cards = []
    for proj in data["projects"]:
        s = data["records"][latest][proj]["summary"] if latest else {}
        project_cards.append(f'''
        <div class="card" data-proj="{proj}">
          <div class="card-title">{proj}</div>
          <div class="card-grid">
            <div><div class="lbl">预售总数</div><div class="val">{s.get('total',0):,}</div></div>
            <div><div class="lbl">已网签</div><div class="val">{s.get('signed',0):,}</div></div>
            <div><div class="lbl">剩余</div><div class="val">{s.get('remaining',0):,}</div></div>
            <div><div class="lbl">去化率</div><div class="val">{s.get('rate',0)*100:.2f}%</div></div>
          </div>
        </div>
        ''')
    cards_html = "\n".join(project_cards)

    html = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>广州新房网签数据</title>
<style>
:root{{--bg:#f5f7fa;--card:#fff;--primary:#1f4e78;--accent:#2e75b6;--text:#333;--muted:#666;--border:#e0e4e8;--up:#d32f2f;--down:#388e3c;--zero:#999;--warn:#fff3cd;--warn-t:#856404;}}
*{{box-sizing:border-box}}
body{{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,"Helvetica Neue",Arial,"PingFang SC","Microsoft YaHei",sans-serif;background:var(--bg);color:var(--text);margin:0;padding:20px;line-height:1.5}}
header{{max-width:1300px;margin:0 auto 20px;background:var(--card);padding:22px 28px;border-radius:10px;box-shadow:0 2px 8px rgba(0,0,0,.06)}}
header h1{{margin:0 0 8px;font-size:24px;color:var(--primary)}}
header p{{margin:6px 0;color:var(--muted);font-size:14px}}
header a{{color:var(--accent);text-decoration:none}}
.controls{{max-width:1300px;margin:0 auto 20px;display:flex;gap:16px;align-items:center;flex-wrap:wrap}}
.controls label{{font-weight:600;color:var(--muted)}}
.controls select{{font-size:16px;padding:8px 12px;border-radius:6px;border:1px solid var(--border);background:#fff}}
.cards{{max-width:1300px;margin:0 auto 20px;display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:16px}}
.card{{background:var(--card);padding:16px 18px;border-radius:10px;box-shadow:0 2px 8px rgba(0,0,0,.06);cursor:pointer;transition:transform .15s,border-color .15s;border:2px solid transparent}}
.card:hover{{transform:translateY(-2px);border-color:var(--accent)}}
.card.active{{border-color:var(--primary)}}
.card-title{{font-weight:700;font-size:16px;color:var(--primary);margin-bottom:10px}}
.card-grid{{display:grid;grid-template-columns:1fr 1fr;gap:10px}}
.card-grid .lbl{{font-size:12px;color:var(--muted)}}
.card-grid .val{{font-size:18px;font-weight:700;color:var(--text)}}
.section{{max-width:1300px;margin:0 auto 28px;background:var(--card);border-radius:10px;box-shadow:0 2px 8px rgba(0,0,0,.06);overflow:hidden}}
.section-header{{padding:16px 20px;background:linear-gradient(90deg,var(--primary),var(--accent));color:#fff;display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:10px}}
.section-header h2{{margin:0;font-size:18px}}
.section-header .note{{font-size:12px;opacity:.9}}
.section-header .totals{{display:flex;gap:18px;font-size:14px}}
.section-header .totals b{{font-size:16px;margin-left:4px}}
table{{width:100%;border-collapse:collapse;font-size:14px}}
th,td{{padding:10px 12px;border:1px solid var(--border);text-align:center}}
th{{background:#f0f4f8;font-weight:600;color:var(--primary);white-space:nowrap}}
td.name{{text-align:left;min-width:180px;word-break:break-word}}
td.num{{text-align:right;font-variant-numeric:tabular-nums}}
tr.total td{{background:#fff3e0;font-weight:700}}
span.na{{color:var(--zero);font-size:12px}}
span.up{{color:var(--up);font-weight:600}}
span.down{{color:var(--down);font-weight:600}}
span.zero{{color:var(--zero)}}
span.rate{{color:var(--primary);font-weight:600}}
.warn{{background:var(--warn);color:var(--warn-t);padding:12px 16px;border-radius:8px;margin:0 auto 20px;max-width:1300px;font-size:14px}}
footer{{max-width:1300px;margin:30px auto;color:var(--muted);font-size:13px}}
footer p{{margin:6px 0}}
@media(max-width:900px){{body{{padding:10px}} .cards{{grid-template-columns:1fr 1fr}} .section{{overflow-x:auto}} table{{min-width:760px}}}}
@media(max-width:600px){{.cards{{grid-template-columns:1fr}}}}
</style>
</head>
<body>
<header>
  <h1>广州新房网签数据</h1>
  <p>数据来源：<a href="https://zfcj.gz.gov.cn/zfcj/fyxx/fdcxmxx/" target="_blank">广州市住房和城乡建设局 · 阳光家缘 · 房地产项目信息</a>（每日自动抓取，仅引用官方数据）</p>
  <p>最后更新：<span id="lastUpdate"></span>｜当前选择日期：<span id="curDate" style="font-weight:700;color:var(--primary)"></span></p>
</header>

<div class="controls">
  <label for="dateSel">选择日期：</label>
  <select id="dateSel"></select>
  <span style="color:var(--muted);font-size:13px">默认显示最新日期；日/周/月环比需至少 2 天数据后自动出现</span>
</div>

<div class="warn">
  <b>数据说明：</b>“已网签数”对应阳光家缘“住宅已售套数”；“剩余未网签”对应“住宅未售套数”；“预售总数”=已售+未售。由于官方 API 不返回“栋号”拆分，楼栋名即官方备案记录中的项目名称。
</div>

<div class="cards" id="cards">
{cards_html}
</div>

<div id="tables"></div>

<footer>
  <p><b>楼盘名称映射：</b>楼栋名严格采用阳光家缘官方备案名称。珑曜上城→珑曜花园；星汇锦城→明颂花园/盛颂花园；繁花里→繁花院；檐屿城→檐屿花园；亚运城环宇熙和→官方暂无“熙和/环宇熙和”备案记录，暂以最新在售官方组团“亚运城B地块B-6~B-9幢住宅”代理。</p>
  <p>本系统每日自动从广州市住建局阳光家缘抓取，所有数据均来自官方公开接口，不做任何人工估算。</p>
</footer>

<script>
const ARCHIVE = {data_json};
const dateSel = document.getElementById('dateSel');
const curDateSpan = document.getElementById('curDate');
const lastUpdate = document.getElementById('lastUpdate');
const tables = document.getElementById('tables');
const cards = document.getElementById('cards');

lastUpdate.textContent = (ARCHIVE.meta.updated || '').replace('T',' ').substring(0,19);
ARCHIVE.dates.slice().reverse().forEach(d => {{ const opt = document.createElement('option'); opt.value = d; opt.textContent = d; dateSel.appendChild(opt); }});

function fmtNum(n){{ if(n===null||n===undefined||n==='') return '<span class="na">—</span>'; return n.toLocaleString(); }}
function fmtDelta(n){{ if(n===null||n===undefined||n==='') return '<span class="na">—</span>'; const sign = n>0?'+':''; return `<span class="num">${{sign}}${{n.toLocaleString()}}</span>`; }}
function fmtPct(v){{ if(v===null||v===undefined||v==='') return '<span class="na">—</span>'; const cls = v>0?'up':(v<0?'down':'zero'); return `<span class="${{cls}}">${{(v*100).toFixed(2)}}%</span>`; }}
function fmtRate(v){{ if(v===null||v===undefined||v==='') return '<span class="na">—</span>'; return `<span class="rate">${{(v*100).toFixed(2)}}%</span>`; }}
function fmtDeltaPct(v){{ if(v===null||v===undefined||v==='') return '<span class="na">—</span>'; const cls = v>0?'up':(v<0?'down':'zero'); const sign = v>0?'+':''; return `<span class="${{cls}}">${{sign}}${{(v*100).toFixed(2)}}%</span>`; }}

function render(){{
  const date = dateSel.value;
  curDateSpan.textContent = date;
  const rec = ARCHIVE.records[date] || {{}};
  tables.innerHTML = '';
  Array.from(cards.children).forEach((c,i) => {{ c.classList.toggle('active', false); }});
  ARCHIVE.projects.forEach((proj, idx) => {{
    const p = rec[proj] || {{buildings:[], summary:{{total:0,signed:0,remaining:0,rate:0,count:0}}}};
    const s = p.summary;
    const note = {json.dumps(mapping_notes, ensure_ascii=False)};
    let rows = p.buildings.map((b, i) => `
      <tr>
        <td class="name">${{b.name}}</td>
        <td>${{b.presell}}</td>
        <td class="num">${{fmtNum(b.total)}}</td>
        <td class="num">${{fmtNum(b.signed)}}</td>
        <td class="num">${{fmtNum(b.remaining)}}</td>
        <td>${{fmtRate(b.rate)}}</td>
        <td class="num">${{fmtDelta(b.day_delta)}}</td>
        <td>${{fmtDeltaPct(b.day_pct)}}</td>
        <td class="num">${{fmtDelta(b.week_delta)}}</td>
        <td>${{fmtDeltaPct(b.week_pct)}}</td>
        <td class="num">${{fmtDelta(b.month_delta)}}</td>
        <td>${{fmtDeltaPct(b.month_pct)}}</td>
      </tr>
    `).join('');
    rows += `
      <tr class="total">
        <td class="name">合计（${{s.count}} 条官方记录）</td>
        <td>—</td>
        <td class="num">${{fmtNum(s.total)}}</td>
        <td class="num">${{fmtNum(s.signed)}}</td>
        <td class="num">${{fmtNum(s.remaining)}}</td>
        <td>${{fmtRate(s.rate)}}</td>
        <td class="num">${{fmtDelta(s.day_delta)}}</td>
        <td>${{fmtDeltaPct(s.day_pct)}}</td>
        <td class="num">${{fmtDelta(s.week_delta)}}</td>
        <td>${{fmtDeltaPct(s.week_pct)}}</td>
        <td class="num">${{fmtDelta(s.month_delta)}}</td>
        <td>${{fmtDeltaPct(s.month_pct)}}</td>
      </tr>
    `;
    const sec = document.createElement('div');
    sec.className = 'section';
    sec.innerHTML = `
      <div class="section-header">
        <h2>${{proj}}</h2>
        <div class="note">${{note[proj]||''}}</div>
        <div class="totals">
          <span>预售总数<b>${{fmtNum(s.total)}}</b></span>
          <span>已网签<b>${{fmtNum(s.signed)}}</b></span>
          <span>剩余<b>${{fmtNum(s.remaining)}}</b></span>
          <span>去化率<b>${{fmtRate(s.rate)}}</b></span>
        </div>
      </div>
      <table>
        <thead>
          <tr>
            <th>楼栋（官方备案名）</th><th>预售证号</th><th>预售总数</th><th>已网签数</th><th>剩余未网签</th><th>去化率</th>
            <th>日新增</th><th>日环比</th><th>周新增(vs上周同日)</th><th>周环比</th><th>月新增(vs上月同日)</th><th>月环比</th>
          </tr>
        </thead>
        <tbody>${{rows}}</tbody>
      </table>
    `;
    tables.appendChild(sec);
  }});
}}

dateSel.addEventListener('change', render);
render();
</script>
</body>
</html>'''
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"[build_site] generated {OUT} ({len(html)} bytes)")

if __name__ == "__main__":
    archive = load_archive()
    data = compute_comparisons(archive)
    build_html(data)
