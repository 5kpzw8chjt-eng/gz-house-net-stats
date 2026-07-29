#!/usr/bin/env python3.11
# -*- coding: utf-8 -*-
"""每日从阳光家缘官方 API 抓取指定楼盘的网签数据，并写入 archive.json。
数据来源：https://zfcj.gz.gov.cn/zfcj/fyxx/fdcxmxx/
实际接口（页面捕获）：/ysqgk/Api/WebApi/fdcxmxxlb.ashx
"""
import json, os, time, sys, re
from datetime import datetime, timedelta
from urllib.parse import urlencode
import requests

BASE_URL = "https://zfcj.gz.gov.cn/ysqgk/Api/WebApi/fdcxmxxlb.ashx"
ARCHIVE = "archive.json"

# 配置：用户名称 -> 官方关键词/过滤条件
PROJECTS = {
    "珑曜上城": {
        "keywords": ["珑曜花园"],
    },
    "星汇锦城": {
        "keywords": ["明颂花园", "盛颂花园"],
    },
    "繁花里": {
        "keywords": ["繁花院"],
    },
    "檐屿城": {
        "keywords": ["檐屿花园"],
    },
    "亚运城环宇熙和": {
        # 官方 API 中未找到“熙和/环宇熙和”备案名；以最新在售的亚运城B地块代理
        "keywords": ["亚运城"],
        "filter": lambda r: r.get("presell") == "20260088" and "B-6~B-9" in r.get("projectName", "")
    }
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36",
    "Referer": "https://zfcj.gz.gov.cn/zfcj/fyxx/fdcxmxx/",
    "Accept": "application/json, text/javascript, */*",
}

def fetch_page(project_name, page=1, page_size=50):
    params = {
        "sProjectName": project_name,
        "sProjectAddress": "",
        "sDeveloper": "",
        "sPresellNo": "",
        "page": page,
        "pageSize": page_size,
    }
    url = f"{BASE_URL}?{urlencode(params)}"
    r = requests.get(url, headers=HEADERS, timeout=30)
    r.raise_for_status()
    return r.json()

def fetch_all(keyword):
    """抓取关键词下所有页，返回原始记录列表。"""
    records = []
    page = 1
    total_page = 1
    while page <= total_page:
        data = fetch_page(keyword, page=page, page_size=50)
        total_page = data.get("totalPage", 0) or 1
        records.extend(data.get("data", []))
        page += 1
        time.sleep(0.3)
    return records

def clean_building_name(name):
    """清理官方名称，保留关键信息。"""
    # 去掉前后空白，保留括号内自编信息
    return re.sub(r"\s+", " ", name).strip()

def build_project_snapshot(alias, cfg):
    records = []
    for kw in cfg["keywords"]:
        records.extend(fetch_all(kw))
    f = cfg.get("filter")
    if f:
        records = [r for r in records if f(r)]
    # 去重：按 projectId
    seen = set()
    uniq = []
    for r in records:
        pid = r.get("projectId")
        if not pid or pid in seen:
            continue
        seen.add(pid)
        uniq.append(r)
    # 排序：按预售证号
    uniq.sort(key=lambda x: x.get("presell", "") or "")

    buildings = []
    for r in uniq:
        sold = int(r.get("houseSoldNum", 0) or 0)
        unsale = int(r.get("houseUnsaleNum", 0) or 0)
        total = sold + unsale
        buildings.append({
            "name": clean_building_name(r.get("projectName", "")),
            "presell": r.get("presell", ""),
            "developer": r.get("developer", ""),
            "address": r.get("projectAddress", ""),
            "total": total,
            "signed": sold,
            "remaining": unsale,
            "rate": round(sold / total, 6) if total > 0 else 0,
        })
    total_all = sum(b["total"] for b in buildings)
    signed_all = sum(b["signed"] for b in buildings)
    remaining_all = sum(b["remaining"] for b in buildings)
    summary = {
        "total": total_all,
        "signed": signed_all,
        "remaining": remaining_all,
        "rate": round(signed_all / total_all, 6) if total_all > 0 else 0,
        "count": len(buildings),
    }
    return {
        "buildings": buildings,
        "summary": summary,
    }

def run(target_date=None):
    if target_date is None:
        target_date = (datetime.now() - timedelta(hours=6)).strftime("%Y-%m-%d")
    # 如果超过今天则取今天；阳光家缘数据为当日累计，建议每天上午抓取
    out = {}
    for alias, cfg in PROJECTS.items():
        print(f"[scraper] fetching {alias} ...")
        try:
            out[alias] = build_project_snapshot(alias, cfg)
        except Exception as e:
            print(f"[scraper] ERROR {alias}: {e}")
            out[alias] = {"buildings": [], "summary": {"total":0,"signed":0,"remaining":0,"rate":0,"count":0}, "error": str(e)}

    # 读取旧归档
    archive = {"meta": {}, "records": {}}
    if os.path.exists(ARCHIVE):
        with open(ARCHIVE, "r", encoding="utf-8") as f:
            archive = json.load(f)
    archive["meta"]["source"] = "https://zfcj.gz.gov.cn/zfcj/fyxx/fdcxmxx/"
    archive["meta"]["updated"] = datetime.now().isoformat()
    archive["meta"]["fetched_date"] = target_date
    archive["records"][target_date] = out

    # 按日期排序，保持 records 字典
    with open(ARCHIVE, "w", encoding="utf-8") as f:
        json.dump(archive, f, ensure_ascii=False, indent=2)
    print(f"[scraper] archived {target_date} -> {ARCHIVE}")
    return archive

if __name__ == "__main__":
    date = sys.argv[1] if len(sys.argv) > 1 else None
    run(date)
