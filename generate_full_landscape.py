#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Generate a standalone AI产业链全景图谱.html from 4 CSV files.

Inputs in this directory:
- nodes.csv
- edges.csv
- company_nodes.csv
- industry_company_edges.csv

Output:
- index.html

No server required. Re-run this script after editing CSV files.
"""
from __future__ import annotations
import csv, html, time
from pathlib import Path
from collections import defaultdict, deque

BASE = Path(__file__).resolve().parent
NODES = BASE / 'nodes.csv'
EDGES = BASE / 'edges.csv'
COMPANY_NODES = BASE / 'company_nodes.csv'
INDUSTRY_COMPANY_EDGES = BASE / 'industry_company_edges.csv'
OUT = BASE / 'index.html'
AUTH_USERNAME = 'ai'
AUTH_PASSWORD = 'ai'


def read_csv(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))


def esc(s) -> str:
    return html.escape(str(s or ''), quote=True)


def int_level(n: dict) -> int:
    try:
        return int(float(n.get('level') or 0))
    except Exception:
        return 0


def main():
    nodes = read_csv(NODES)
    edges = read_csv(EDGES)
    company_nodes = read_csv(COMPANY_NODES)
    industry_company_edges = read_csv(INDUSTRY_COMPANY_EDGES)

    node = {n['id']: n for n in nodes}
    company = {c['id']: c for c in company_nodes}

    children: dict[str, list[str]] = defaultdict(list)
    parent: dict[str, str] = {}
    for e in edges:
        if e.get('relation') == 'is_a' and e.get('source') in node and e.get('target') in node:
            children[e['target']].append(e['source'])
            parent[e['source']] = e['target']

    for k in list(children):
        children[k] = sorted(set(children[k]), key=lambda x: (int_level(node[x]), node[x].get('name', x)))

    companies_by_industry: dict[str, list[dict]] = defaultdict(list)
    seen_rel = set()
    for e in industry_company_edges:
        if e.get('source') not in node or e.get('target') not in company:
            continue
        key = (e.get('source'), e.get('target'), e.get('source_industry'), e.get('source_direction'), e.get('remark'))
        if key in seen_rel:
            continue
        seen_rel.add(key)
        c = company[e['target']]
        row = {
            'company_id': e['target'],
            'company_name': c.get('name') or e.get('target_name'),
            'stock_code': c.get('stock_code') or e.get('stock_code'),
            'market': c.get('market', ''),
            'source_layer': e.get('source_layer', ''),
            'source_industry': e.get('source_industry', ''),
            'source_direction': e.get('source_direction', ''),
            'remark': e.get('remark', ''),
        }
        companies_by_industry[e['source']].append(row)

    for nid in list(companies_by_industry):
        companies_by_industry[nid].sort(key=lambda r: (r['source_industry'], r['source_direction'], r['company_name']))

    roots = [n['id'] for n in nodes if n['id'] not in parent]
    root_id = 'ai_industry' if 'ai_industry' in node else (roots[0] if roots else (nodes[0]['id'] if nodes else ''))

    # Compute depth for stats.
    depth = {n['id']: None for n in nodes}
    q = deque()
    for r in roots:
        depth[r] = 0
        q.append(r)
    while q:
        u = q.popleft()
        for v in children.get(u, []):
            nd = (depth[u] or 0) + 1
            if depth[v] is None or nd < depth[v]:
                depth[v] = nd
                q.append(v)
    for n in nodes:
        if depth[n['id']] is None:
            depth[n['id']] = int_level(n)

    rendered = set()

    def company_tags(nid: str) -> str:
        rows = companies_by_industry.get(nid, [])
        if not rows:
            return '<div class="company-row empty">暂无匹配A股标的</div>'
        tags = []
        for r in rows:
            title = f"{r['source_industry']} / {r['source_direction']}｜{r['remark']}"
            tags.append(f'<span class="company-tag" title="{esc(title)}">{esc(r["company_name"])}</span>')
        return '<div class="company-row">' + ''.join(tags) + '</div>'

    def render_subtree(nid: str, level: int = 0) -> str:
        if nid not in node:
            return ''
        rendered.add(nid)
        cs = children.get(nid, [])
        if not cs:
            return (
                f'<div class="leaf node-depth-{level}" data-id="{esc(nid)}">'
                f'<div class="leaf-title">{esc(node[nid]["name"])}</div>'
                f'{company_tags(nid)}'
                f'</div>'
            )
        inner = ''.join(render_subtree(c, level + 1) for c in cs)
        return (
            f'<div class="group node-depth-{level}" data-id="{esc(nid)}">'
            f'<div class="group-title"><span>{esc(node[nid]["name"])}</span></div>'
            f'<div class="group-body">{inner}</div>'
            f'</div>'
        )

    def stage_class(nid: str) -> str:
        if nid == 'ai_infrastructure_industry':
            return 'infra'
        if nid == 'ai_terminal_industry':
            return 'terminal'
        if nid == 'ai_application_industry':
            return 'application'
        return 'other'

    def render_stage(nid: str) -> str:
        rendered.add(nid)
        cs = children.get(nid, [])
        if nid == 'ai_infrastructure_industry':
            preferred = ['ai_server_industry', 'data_center_industry', 'cloud_service_industry', 'large_model_industry', 'semiconductor_chip_industry']
            cs = [x for x in preferred if x in cs] + [x for x in cs if x not in preferred]
        cards = []
        for c in cs:
            rendered.add(c)
            extra_cls = ' semiconductor-wide' if nid == 'ai_infrastructure_industry' and c == 'semiconductor_chip_industry' else ''
            body = ''.join(render_subtree(gc, 1) for gc in children.get(c, [])) if children.get(c) else company_tags(c)
            cards.append(
                f'<article class="major-card{extra_cls}" data-id="{esc(c)}">'
                f'<h3>{esc(node[c]["name"])}</h3>'
                f'<div class="major-body">{body}</div>'
                f'</article>'
            )
        return (
            f'<section class="stage {stage_class(nid)}" data-id="{esc(nid)}">'
            f'<div class="stage-head"><h2>{esc(node[nid]["name"])}</h2><p>{len(cs)} 个一级分支</p></div>'
            f'<div class="major-grid">{"".join(cards)}</div>'
            f'</section>'
        )

    top_children = children.get(root_id, [])
    preferred_top = ['ai_infrastructure_industry', 'ai_terminal_industry', 'ai_application_industry']
    top_children = [x for x in preferred_top if x in top_children] + [x for x in top_children if x not in preferred_top]
    stages_html = ''.join(render_stage(t) for t in top_children)

    missing = [n['id'] for n in nodes if n['id'] not in rendered and n['id'] != root_id]
    appendix = ''
    if missing:
        appendix = (
            '<section class="stage appendix"><div class="stage-head"><h2>其他节点</h2>'
            f'<p>{len(missing)} 个节点</p></div><div class="major-grid">'
            + ''.join(f'<article class="major-card">{render_subtree(m, 0)}</article>' for m in missing)
            + '</div></section>'
        )

    total_company_edges = len(industry_company_edges)
    generated = time.strftime('%Y-%m-%d %H:%M:%S')

    css = r'''
:root{--bg:#f8f5ed;--ink:#17172f;--muted:#69677a;--purple:#5b2bd9;--purple2:#7c3aed;--green:#0d7d68;--blue:#2563eb;--orange:#e87524;--card:#fffdfa;--line:#2b2368;--soft:#eee9ff}
*{box-sizing:border-box}html,body{margin:0;background:var(--bg);color:var(--ink);font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Microsoft YaHei",Arial,sans-serif}.toolbar{position:sticky;top:0;z-index:20;display:flex;align-items:center;gap:8px;padding:8px 14px;background:rgba(248,245,237,.95);border-bottom:2px solid var(--purple);backdrop-filter:blur(8px)}.toolbar b{color:#21164f;margin-right:8px}.toolbar button{height:30px;border:1px solid var(--purple);background:#fff;color:#21164f;border-radius:8px;padding:0 10px;font-weight:850;cursor:pointer}.toolbar button:hover{background:#eee9ff}.toolbar .zoom-label{font-size:13px;color:var(--muted);font-weight:800}.zoom-wrap{transform-origin:top left;transition:transform .12s ease;width:max-content}.page{width:2600px;margin:0 auto;padding:32px 38px 36px}.top{display:grid;grid-template-columns:1fr auto 1fr;align-items:start;gap:18px;border-bottom:5px solid var(--purple);padding-bottom:17px;margin-bottom:18px}.brand{font-size:25px;font-weight:950;color:#21164f;letter-spacing:.02em}.title{text-align:center}.title h1{margin:0;font-size:56px;line-height:1.05;letter-spacing:.08em;font-weight:950;color:#21164f}.title p{margin:9px 0 0;font-size:17px;color:var(--muted);font-weight:650}.meta{text-align:right;font-size:15px;color:#21164f;font-weight:850;line-height:1.55}.legend{display:flex;align-items:center;justify-content:center;gap:16px;margin:10px 0 18px;color:#31295e;font-weight:900}.legend span{display:inline-flex;align-items:center;border:2px solid var(--purple);background:#fff;border-radius:999px;padding:8px 15px;font-size:15px}.legend b{font-size:24px;color:var(--purple)}.stage{border:3px solid var(--purple);background:rgba(255,255,255,.56);padding:12px;margin-bottom:18px}.stage.infra{--accent:var(--green)}.stage.terminal{--accent:var(--blue)}.stage.application{--accent:var(--orange)}.stage.appendix{--accent:#64748b}.stage-head{display:flex;align-items:flex-end;justify-content:space-between;border-bottom:2px solid var(--purple);padding:2px 4px 9px;margin-bottom:12px}.stage-head h2{margin:0;font-size:30px;letter-spacing:.04em;color:#21164f}.stage-head h2:before{content:"";display:inline-block;width:10px;height:28px;background:var(--accent);margin-right:9px;vertical-align:-4px}.stage-head p{margin:0;color:var(--muted);font-size:13px}.major-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px}.stage.infra .major-grid{grid-template-columns:repeat(4,minmax(0,1fr))}.stage.infra .major-card.semiconductor-wide{grid-column:1 / -1}.stage.infra .major-card.semiconductor-wide>.major-body{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:8px}.stage.infra .major-card.semiconductor-wide .group-body{grid-template-columns:repeat(auto-fit,minmax(170px,1fr))}.stage.terminal .major-grid{grid-template-columns:repeat(5,minmax(0,1fr))}.stage.application .major-grid{grid-template-columns:repeat(6,minmax(0,1fr))}.major-card{background:var(--card);border:2px solid var(--line);padding:8px;min-width:0}.major-card>h3{margin:0 0 8px;text-align:center;color:var(--purple2);font-size:17px;border-bottom:1px solid #d7cffc;padding-bottom:5px}.major-body{display:grid;gap:7px}.group{border:1px solid #d8d4ea;background:#fbfbff;padding:6px;margin-bottom:6px}.group-title{font-size:13px;font-weight:950;color:#21164f;border-bottom:1px solid #e3def8;padding-bottom:4px;margin-bottom:5px}.group-body{display:grid;grid-template-columns:repeat(auto-fit,minmax(185px,1fr));gap:6px}.group .group{background:#fff;border-color:#e3e0ef}.group .group .group-body{grid-template-columns:repeat(auto-fit,minmax(160px,1fr))}.leaf{border:1px solid #dcdce8;background:#fff;border-radius:5px;padding:5px;min-width:0}.leaf-title{font-size:12.5px;font-weight:950;color:#22223b;margin-bottom:4px;line-height:1.25}.company-row{display:flex;flex-wrap:wrap;gap:3px}.company-row.empty{font-size:10px;color:#aaa}.company-tag{display:inline-flex;align-items:center;gap:3px;border:1px solid #ddd;background:#fff;border-radius:4px;padding:2px 4px;line-height:1.12;max-width:100%;font-size:10.5px;color:#222;font-weight:800}.footer{border-top:4px solid var(--purple);padding-top:10px;display:flex;justify-content:space-between;color:#4c4771;font-size:13px;font-weight:700}.node-depth-4 .leaf-title,.node-depth-5 .leaf-title{font-size:11.5px}.auth-overlay{position:fixed;inset:0;z-index:9999;display:flex;align-items:center;justify-content:center;background:linear-gradient(135deg,#f8f5ed,#eee9ff);padding:20px}.auth-card{width:min(380px,100%);background:#fff;border:2px solid var(--purple);border-radius:18px;box-shadow:0 18px 50px rgba(33,22,79,.18);padding:24px}.auth-card h2{margin:0 0 6px;color:#21164f;font-size:24px}.auth-card p{margin:0 0 18px;color:var(--muted);font-size:13px}.auth-card label{display:block;margin:12px 0 6px;font-weight:850;color:#21164f}.auth-card input{width:100%;height:40px;border:1px solid #d7cffc;border-radius:10px;padding:0 12px;font-size:15px}.auth-card button{width:100%;height:42px;margin-top:18px;border:0;border-radius:10px;background:var(--purple);color:#fff;font-weight:950;cursor:pointer}.auth-error{min-height:20px;margin-top:10px;color:#dc2626;font-size:13px;font-weight:800}.auth-hidden{display:none!important}body.auth-locked .toolbar,body.auth-locked .zoom-wrap{display:none}@media(max-width:1200px){.page{width:1600px}.stage.infra .major-grid,.stage.terminal .major-grid,.stage.application .major-grid{grid-template-columns:repeat(3,minmax(0,1fr))}}
'''

    html_text = f'''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"/><meta name="viewport" content="width=device-width,initial-scale=1"/><title>AI产业链全景图谱</title><style>{css}</style></head><body class="auth-locked"><div class="auth-overlay" id="authOverlay"><form class="auth-card" id="authForm"><h2>访问验证</h2><p>请输入用户名和密码查看 AI 产业链全景图谱。</p><label for="authUser">用户名</label><input id="authUser" name="username" autocomplete="username" autofocus/><label for="authPass">密码</label><input id="authPass" name="password" type="password" autocomplete="current-password"/><button type="submit">登录</button><div class="auth-error" id="authError"></div></form></div><div class="toolbar"><b>AI产业链全景图谱</b><button id="zoomOut">缩小</button><button id="zoomIn">放大</button><button id="resetZoom">重置</button><span class="zoom-label" id="zoomLabel">100%</span></div><div class="zoom-wrap" id="zoomWrap"><main class="page"><header class="top"><div class="brand">AI产业链 Graph</div><div class="title"><h1>AI产业链全景图谱</h1><p>由 nodes.csv、edges.csv、company_nodes.csv、industry_company_edges.csv 生成</p></div><div class="meta">产业节点 {len(nodes)}<br/>公司节点 {len(company_nodes)}<br/>产业-公司关系 {total_company_edges}</div></header><div class="legend"><span>人工智能基础设施</span><b>·</b><span>人工智能终端</span><b>·</b><span>人工智能应用</span></div>{stages_html}{appendix}<div class="footer"><span>大框表示产业层级分区，内部小框表示下级产业，企业标签来自 company_nodes.csv 与 industry_company_edges.csv。</span><span>生成时间：{esc(generated)}</span></div></main></div><script>const __AUTH_USER={AUTH_USERNAME!r};const __AUTH_PASS={AUTH_PASSWORD!r};const __AUTH_KEY="ai_atlas_auth_ok";const __authOverlay=document.getElementById("authOverlay");const __authForm=document.getElementById("authForm");const __authError=document.getElementById("authError");function __unlock(){{document.body.classList.remove("auth-locked");__authOverlay.classList.add("auth-hidden");}}if(sessionStorage.getItem(__AUTH_KEY)==="1"){{__unlock();}}__authForm.addEventListener("submit",(e)=>{{e.preventDefault();const u=document.getElementById("authUser").value.trim();const p=document.getElementById("authPass").value;if(u===__AUTH_USER&&p===__AUTH_PASS){{sessionStorage.setItem(__AUTH_KEY,"1");__unlock();}}else{{__authError.textContent="用户名或密码错误";document.getElementById("authPass").value="";document.getElementById("authPass").focus();}}}});let __scale=1;const __wrap=document.getElementById("zoomWrap");const __label=document.getElementById("zoomLabel");function __applyZoom(){{__wrap.style.transform="scale("+__scale+")";__label.textContent=Math.round(__scale*100)+"%";}}document.getElementById("zoomIn").onclick=()=>{{__scale=Math.min(2,__scale+0.1);__applyZoom();}};document.getElementById("zoomOut").onclick=()=>{{__scale=Math.max(0.35,__scale-0.1);__applyZoom();}};document.getElementById("resetZoom").onclick=()=>{{__scale=1;__applyZoom();}};</script></body></html>'''
    OUT.write_text(html_text, encoding='utf-8')
    print(f'wrote {OUT} from 4 CSV files: industry_nodes={len(nodes)}, industry_edges={len(edges)}, companies={len(company_nodes)}, industry_company_edges={len(industry_company_edges)}')

if __name__ == '__main__':
    main()
