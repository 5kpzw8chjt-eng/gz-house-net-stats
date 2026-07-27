#!/bin/bash
# 每日自动抓取阳光家缘官方数据 -> 归档 -> 重新生成网站 -> 推送到 GitHub Pages 仓库
cd /workspace
python3.11 scraper.py
python3.11 build_site.py
# GitHub Pages 需要 index.html 作为入口
cp "广州新房网签数据.html" index.html
# 推送到发布仓库（仅当已配置 git 远程）
if git rev-parse --is-inside-work-tree >/dev/null 2>&1 && git remote get-url origin >/dev/null 2>&1; then
  git add -A
  git commit -m "daily update $(date +%F)" || true
  git push origin main || true
fi
