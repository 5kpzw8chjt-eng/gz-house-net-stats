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
            prev = _prev_date(date, dates)
            wstart = _week_monday(date, dates)
            mstart = _month_first(date, dates)
            bld_out = []
            for b in snap.get("buildings", []):
                bld_out.append(_attach_compare(b, date, prev, wstart, mstart, records, proj))
            summary = snap.get("summary", {}).copy()
            summary = _attach_compare(summary, date, prev, wstart, mstart, records, proj, is_summary=True)
            summary["count"] = len(bld_out)
            out["records"][date][proj] = {"buildings": bld_out, "summary": summary}
    return out


def _prev_date(date, dates):
    idx = dates.index(date)
    return dates[idx-1] if idx > 0 else None


def _week_monday(date, dates):
    d = datetime.strptime(date, "%Y-%m-%d")
    mon = d - timedelta(days=d.weekday())
    mon_str = mon.strftime("%Y-%m-%d")
    candidates = [dd for dd in dates if mon_str <= dd <= date]
    if candidates:
        return candidates[0]
    return None


def _month_first(date, dates):
    d = datetime.strptime(date, "%Y-%m-%d")
    first = d.replace(day=1)
    first_str = first.strftime("%Y-%m-%d")
    candidates = [dd for dd in dates if first_str <= dd <= date]
    if candidates:
        return candidates[0]
    return None


def _attach_compare(item, date, prev, wstart, mstart, records, proj, is_summary=False):
    out = dict(item)
    curr = item.get("signed", 0) or 0
    if prev and prev != date and prev in records and proj in records[prev]:
        ref_val = _get_ref_signed(prev, records, proj, item, is_summary)
        if ref_val is not None:
            out["day_delta"] = curr - ref_val
            out["day_pct"] = round((curr - ref_val) / ref_val, 6) if ref_val > 0 else (0.0 if curr == ref_val else None)
        else:
            out["day_delta"] = None
            out["day_pct"] = None
    else:
        out["day_delta"] = None
        out["day_pct"] = None
    day_delta = out.get("day_delta")
    if wstart and wstart in records and proj in records[wstart]:
        if wstart != date:
            ref_val = _get_ref_signed(wstart, records, proj, item, is_summary)
            if ref_val is not None:
                out["week_delta"] = curr - ref_val
                out["week_pct"] = round((curr - ref_val) / ref_val, 6) if ref_val > 0 else (0.0 if curr == ref_val else None)
            else:
                out["week_delta"] = None
                out["week_pct"] = None
        else:
            out["week_delta"] = day_delta
            out["week_pct"] = out.get("day_pct")
    else:
        out["week_delta"] = None
        out["week_pct"] = None
    if mstart and mstart in records and proj in records[mstart]:
        if mstart != date:
            ref_val = _get_ref_signed(mstart, records, proj, item, is_summary)
            if ref_val is not None:
                out["month_delta"] = curr - ref_val
                out["month_pct"] = round((curr - ref_val) / ref_val, 6) if ref_val > 0 else (0.0 if curr == ref_val else None)
            else:
                out["month_delta"] = None
                out["month_pct"] = None
        else:
            out["month_delta"] = day_delta
            out["month_pct"] = out.get("day_pct")
    else:
        out["month_delta"] = None
        out["month_pct"] = None
    return out


def _get_ref_signed(ref_date, records, proj, item, is_summary):
    ref_rec = records[ref_date][proj]
    if is_summary:
        ref = ref_rec.get("summary", {})
    else:
        ref = next((x for x in ref_rec.get("buildings", []) if x.get("name") == item.get("name")), None)
    if ref is None:
        return None
    return ref.get("signed", 0) or 0


def build_html(data):
    dates = data["dates"]
    latest = dates[-1] if dates else ""
    data_json = json.dumps(data, ensure_ascii=False, indent=2)
    data_json = data_json.replace("</", "<\/")
    mapping_notes = {
        "珑曜上城": "官方备案名：珑曜花园",
        "星汇锦城": "官方备案名：盛颂花园（越秀·大学·星汇锦城）",
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
:root{{--bg:#f5f7fa;--card:#fff;--primary:#1f4e78;--accent:#2e75b6;--text:#333;--muted:#666;--border:#e0e4e8;--up:#d32f2f;--down:#388e3c;--zero:#999;--warn:#fff3cd;--warn-t:#856404;--shadow:0 2px 8px rgba(0,0,0,.06);}}
*{{box-sizing:border-box}}
body{{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,"Helvetica Neue",Arial,"PingFang SC","Microsoft YaHei",sans-serif;background:var(--bg);color:var(--text);margin:0;padding:20px;line-height:1.5}}
header{{max-width:1300px;margin:0 auto 20px;background:var(--card);padding:22px 28px;border-radius:10px;box-shadow:var(--shadow)}}
header h1{{margin:0 0 8px;font-size:24px;color:var(--primary)}}
header p{{margin:6px 0;color:var(--muted);font-size:14px}}
header a{{color:var(--accent);text-decoration:none}}
.controls{{max-width:1300px;margin:0 auto 20px;display:flex;gap:16px;align-items:center;flex-wrap:wrap}}
.controls label{{font-weight:600;color:var(--muted)}}
.controls select{{font-size:16px;padding:8px 12px;border-radius:6px;border:1px solid var(--border);background:#fff}}
.cards{{max-width:1300px;margin:0 auto 20px;display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:16px}}
.card{{background:var(--card);padding:16px 18px;border-radius:10px;box-shadow:var(--shadow);cursor:pointer;transition:transform .15s,border-color .15s;border:2px solid transparent}}
.card:hover{{transform:translateY(-2px);border-color:var(--accent)}}
.card.active{{border-color:var(--primary)}}
.card-title{{font-weight:700;font-size:16px;color:var(--primary);margin-bottom:10px}}
.card-grid{{display:grid;grid-template-columns:1fr 1fr;gap:10px}}
.card-grid .lbl{{font-size:12px;color:var(--muted)}}
.card-grid .val{{font-size:18px;font-weight:700;color:var(--text)}}
.section{{max-width:1300px;margin:0 auto 28px;background:var(--card);border-radius:10px;box-shadow:var(--shadow);overflow:hidden}}
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
.bld-link{{color:var(--accent);cursor:pointer;text-decoration:underline}}
.bld-link:hover{{color:var(--primary)}}
.modal-overlay{{position:fixed;inset:0;background:rgba(0,0,0,.5);z-index:1000;display:none;align-items:center;justify-content:center;padding:20px}}
.modal-overlay.open{{display:flex}}
.modal{{background:var(--card);border-radius:12px;box-shadow:0 10px 40px rgba(0,0,0,.2);width:min(1100px,100%);max-height:90vh;display:flex;flex-direction:column;overflow:hidden}}
.modal-header{{padding:16px 20px;background:var(--primary);color:#fff;display:flex;justify-content:space-between;align-items:center}}
.modal-header h3{{margin:0;font-size:18px}}
.modal-header .close{{cursor:pointer;font-size:22px;line-height:1}}
.modal-subtabs{{display:flex;gap:8px;padding:12px 20px 0;border-bottom:1px solid var(--border);flex-wrap:wrap}}
.modal-subtabs .subtab{{padding:6px 14px;border-radius:6px 6px 0 0;cursor:pointer;border:1px solid transparent;border-bottom:none;background:#f0f4f8;color:var(--muted)}}
.modal-subtabs .subtab.active{{background:var(--card);color:var(--primary);border-color:var(--border);font-weight:600}}
.modal-body{{padding:16px 20px;overflow:auto;flex:1}}
.sales-legend{{display:flex;gap:12px;flex-wrap:wrap;margin-bottom:14px;font-size:13px;color:var(--muted)}}
.legend-item{{display:flex;align-items:center;gap:5px}}
.legend-color{{width:16px;height:16px;border-radius:4px;border:1px solid #ccc}}
.sales-table{{border-collapse:collapse;width:auto;min-width:100%;font-size:13px}}
.sales-table th,.sales-table td{{border:1px solid var(--border);padding:4px 6px;text-align:center;white-space:nowrap}}
.sales-table th{{background:#f8fafc;position:sticky;top:0;z-index:2}}
.sales-table td.floor-label{{background:#f0f4f8;font-weight:600;color:var(--primary);position:sticky;left:0;z-index:1}}
.room-cell{{min-width:64px;height:46px;vertical-align:middle;cursor:default;border-radius:3px}}
.room-cell .unit{{font-weight:700;font-size:12px}}
.room-cell .type{{font-size:10px;color:rgba(0,0,0,.65);margin-top:1px}}
.status-3{{background:#4caf50;color:#fff}}
.status-4{{background:#d32f2f;color:#fff}}
.status-5{{background:#ff9800;color:#fff}}
.status-1{{background:#9e9e9e;color:#fff}}
.status-2{{background:#42a5f5;color:#fff}}
.status-0{{background:#e0e0e0;color:#666}}
.room-tip{{position:fixed;background:rgba(0,0,0,.85);color:#fff;padding:8px 10px;border-radius:6px;font-size:12px;pointer-events:none;z-index:2000;display:none;max-width:220px;line-height:1.5}}
.no-detail{{color:var(--muted);padding:30px;text-align:center}}
@media(max-width:900px){{body{{padding:10px}} .cards{{grid-template-columns:1fr 1fr}} .section{{overflow-x:auto}} table{{min-width:760px}} .modal{{width:100%;max-height:95vh}}}}
@media(max-width:600px){{.cards{{grid-template-columns:1fr}} .modal-subtabs{{gap:4px}}}}
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
  <span style="color:var(--muted);font-size:13px">默认显示最新日期；日/周/月环比需至少 2 天数据后自动出现；点击楼栋名查看销控表</span>
</div>

<div class="warn">
  <b>数据说明：</b>“已网签数”对应阳光家缘“住宅已售套数”；“剩余未网签”对应“住宅未售套数”；“预售总数”=已售+未售。点击楼栋名称可查看官方销控表（楼层×房号）。由于官方 API 不返回“栋号”拆分，楼栋名即官方备案记录中的项目名称。
</div>

<div class="cards" id="cards">
{cards_html}
</div>

<div id="tables"></div>

<div class="modal-overlay" id="modalOverlay">
  <div class="modal">
    <div class="modal-header">
      <h3 id="modalTitle">楼栋销控表</h3>
      <span class="close" onclick="closeModal()">&times;</span>
    </div>
    <div class="modal-subtabs" id="modalSubtabs"></div>
    <div class="modal-body" id="modalBody">
      <div class="sales-legend" id="salesLegend"></div>
      <div id="salesTableWrap"></div>
    </div>
  </div>
</div>
<div class="room-tip" id="roomTip"></div>

<footer>
  <p><b>楼盘名称映射：</b>楼栋名严格采用阳光家缘官方备案名称。珑曜上城→珑曜花园；星汇锦城→盛颂花园；繁花里→繁花院；檐屿城→檐屿花园；亚运城环宇熙和→官方暂无“熙和/环宇熙和”备案记录，暂以最新在售官方组团“亚运城B地块B-6~B-9幢住宅”代理。</p>
  <p>本系统每日自动从广州市住建局阳光家缘抓取，所有数据均来自官方公开接口，不做任何人工估算。</p>
</footer>

<script>
const ARCHIVE = {data_json};
const dateSel = document.getElementById('dateSel');
const curDateSpan = document.getElementById('curDate');
const lastUpdate = document.getElementById('lastUpdate');
const tables = document.getElementById('tables');
const cards = document.getElementById('cards');
const modalOverlay = document.getElementById('modalOverlay');
const modalTitle = document.getElementById('modalTitle');
const modalSubtabs = document.getElementById('modalSubtabs');
const salesLegend = document.getElementById('salesLegend');
const salesTableWrap = document.getElementById('salesTableWrap');
const roomTip = document.getElementById('roomTip');

const STATUS_MAP = {{
  3: {{label:'可售', cls:'status-3'}},
  4: {{label:'已售', cls:'status-4'}},
  5: {{label:'限制销售', cls:'status-5'}},
  1: {{label:'未纳入/其他', cls:'status-1'}},
  2: {{label:'抵押/查封', cls:'status-2'}}
}};

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
        <td class="name"><span class="bld-link" onclick="openSalesControl('${{proj}}','${{b.name.replace(/'/g,"\\'")}}')">${{b.name}}</span></td>
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
            <th>楼栋（官方备案名，点击查看销控表）</th><th>预售证号</th><th>预售总数</th><th>已网签数</th><th>剩余未网签</th><th>去化率</th>
            <th>日新增</th><th>日环比</th><th>本周累计新增</th><th>周环比</th><th>本月累计新增</th><th>月环比</th>
          </tr>
        </thead>
        <tbody>${{rows}}</tbody>
      </table>
    `;
    tables.appendChild(sec);
  }});
}}

let currentSubUnits = [];
let currentSubIndex = 0;

function openSalesControl(proj, bldName){{
  const date = dateSel.value;
  const p = (ARCHIVE.records[date] || {{}})[proj];
  if (!p) return;
  const b = p.buildings.find(x => x.name === bldName);
  if (!b) return;
  const detail = b.detail || {{}};
  const units = detail.units || {{}};
  const bids = Object.keys(units);
  if (bids.length === 0){{
    modalTitle.textContent = `${{proj}} · ${{bldName}}`;
    modalSubtabs.innerHTML = '';
    salesLegend.innerHTML = '';
    salesTableWrap.innerHTML = '<div class="no-detail">暂无销控表楼层数据（可能官方接口暂未返回）</div>';
    modalOverlay.classList.add('open');
    return;
  }}
  currentSubUnits = bids.map(bid => ({{bid, ...units[bid]}}));
  currentSubIndex = 0;
  modalTitle.textContent = `${{proj}} · ${{bldName}}（预售证 ${{b.presell}}）`;
  renderSubtabs();
  renderSalesTable(currentSubUnits[0]);
  modalOverlay.classList.add('open');
}}

function renderSubtabs(){{
  if (currentSubUnits.length <= 1){{
    modalSubtabs.innerHTML = '';
    return;
  }}
  modalSubtabs.innerHTML = currentSubUnits.map((u, i) => `
    <div class="subtab ${{i===currentSubIndex?'active':''}}" onclick="switchSubtab(${{i}})">${{u.name}}</div>
  `).join('');
}}

window.switchSubtab = function(i){{
  currentSubIndex = i;
  renderSubtabs();
  renderSalesTable(currentSubUnits[i]);
}}

function renderSalesTable(unit){{
  const legendItems = [
    {{cls:'status-3', label:'可售'}},
    {{cls:'status-4', label:'已售/已签约'}},
    {{cls:'status-5', label:'限制销售'}},
    {{cls:'status-1', label:'未纳入/其他'}},
    {{cls:'status-2', label:'抵押/查封'}},
    {{cls:'status-0', label:'未知'}}
  ];
  salesLegend.innerHTML = legendItems.map(item => `
    <div class="legend-item"><div class="legend-color ${{item.cls}}"></div><span>${{item.label}}</span></div>
  `).join('');

  const floors = unit.floors || [];
  if (floors.length === 0){{
    salesTableWrap.innerHTML = '<div class="no-detail">该楼栋暂无销控表数据</div>';
    return;
  }}

  const sorted = floors.slice().sort((a,b) => Number(b.group) - Number(a.group));
  const colSet = new Set();
  sorted.forEach(f => f.groupData.forEach(r => colSet.add(r.unitNum)));
  // 按完整房号字符串排序（如 2901 < 3001 < 3101 < 3201）
  const cols = Array.from(colSet).sort();

  let html = '<table class="sales-table"><thead><tr><th class="floor-label">楼层</th>';
  cols.forEach(c => {{ html += `<th>${{c}}</th>`; }});
  html += '</tr></thead><tbody>';

  sorted.forEach(f => {{
    html += `<tr><td class="floor-label">${{f.group}}层</td>`;
    const map = {{}};
    f.groupData.forEach(r => {{ map[r.unitNum] = r; }});
    cols.forEach(c => {{
      const r = map[c];
      if (!r){{
        html += '<td></td>';
      }} else {{
        let st;
        if (r.preSellStatus === 1) st = {{cls:'status-4', label:'已售/已签约'}};
        else if (r.preSellStatus === 0) st = {{cls:'status-3', label:'可售'}};
        else st = STATUS_MAP[r.status] || {{cls:'status-0', label:'未知'}};
        html += `<td class="room-cell ${{st.cls}}" data-info='${{JSON.stringify(r).replace(/'/g,"&#39;")}}'>
          <div class="unit">${{r.unitNum}}</div>
          <div class="type">${{r.unitType||r.houseFunction||''}}</div>
        </td>`;
      }}
    }});
    html += '</tr>';
  }});
  html += '</tbody></table>';
  salesTableWrap.innerHTML = html;

  salesTableWrap.querySelectorAll('.room-cell').forEach(cell => {{
    cell.addEventListener('mouseenter', e => {{
      const r = JSON.parse(cell.getAttribute('data-info'));
      let st;
      if (r.preSellStatus === 1) st = {{label:'已售/已签约'}};
      else if (r.preSellStatus === 0) st = {{label:'可售'}};
      else st = STATUS_MAP[r.status] || {{label:'未知'}};
      roomTip.innerHTML = `
        <b>${{r.unitNum}}</b>（${{r.floorNum}}层）<br/>
        类型：${{r.houseFunction||'—'}} ${{r.unitType||''}}<br/>
        建筑面积：${{r.totalArea}}㎡<br/>
        套内面积：${{r.inArea}}㎡<br/>
        状态：${{st.label}}
      `;
      roomTip.style.display = 'block';
    }});
    cell.addEventListener('mousemove', e => {{
      roomTip.style.left = (e.clientX + 12) + 'px';
      roomTip.style.top = (e.clientY + 12) + 'px';
    }});
    cell.addEventListener('mouseleave', () => {{ roomTip.style.display = 'none'; }});
  }});
}}

window.closeModal = function(){{
  modalOverlay.classList.remove('open');
}}

modalOverlay.addEventListener('click', e => {{
  if (e.target === modalOverlay) closeModal();
}});
document.addEventListener('keydown', e => {{
  if (e.key === 'Escape') closeModal();
}});

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
