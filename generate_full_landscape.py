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
AUTH_PASSWORD = 'ai-atlas@finstep'


def read_csv(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))


def esc(s) -> str:
    return html.escape(str(s or ''), quote=True)


def short_company_name(name: str) -> str:
    """Use company abbreviation text as a logo substitute in the landscape."""
    n = str(name or '').strip()
    suffixes = [
        '股份有限公司','集团股份','集团有限公司','控股有限公司','科技股份','技术股份',
        '有限公司','股份','集团','控股','科技','技术','信息','软件','电子','智能','有限'
    ]
    for suf in suffixes:
        if len(n) > 4 and n.endswith(suf):
            n = n[:-len(suf)]
    return n[:9] + ('…' if len(n) > 9 else '')


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

    subtree_company_cache: dict[str, int] = {}

    def subtree_company_count(nid: str) -> int:
        if nid in subtree_company_cache:
            return subtree_company_cache[nid]
        total = len(companies_by_industry.get(nid, []))
        for cid in children.get(nid, []):
            total += subtree_company_count(cid)
        subtree_company_cache[nid] = total
        return total

    def count_class(count: int) -> str:
        if count >= 40:
            return ' count-xl'
        if count >= 24:
            return ' count-lg'
        if count >= 12:
            return ' count-md'
        if count > 0:
            return ' count-sm'
        return ' count-empty'

    def span_class(nid: str) -> str:
        total = subtree_company_count(nid)
        branch_count = len(children.get(nid, []))
        if total >= 180 or branch_count >= 8:
            return ' span-xl'
        if total >= 90 or branch_count >= 5:
            return ' span-lg'
        if total >= 36 or branch_count >= 3:
            return ' span-md'
        return ' span-sm'

    def company_tags(nid: str) -> str:
        rows = companies_by_industry.get(nid, [])
        if not rows:
            return '<div class="company-row empty">暂无匹配公司</div>'
        tags = []
        for r in rows:
            title = f"{r['company_name']}｜{r['stock_code']}｜{r['source_industry']} / {r['source_direction']}｜{r['remark']}"
            market = r.get('market') or ''
            market_cls = ' market-foreign' if ('外资' in market or '美' in market) else (' market-hk' if '港' in market else (' market-tw' if '台' in market else (' market-growth' if ('科创' in market or '创业' in market) else ' market-a')))
            tags.append(f'<span class="company-tag{market_cls}" title="{esc(title)}">{esc(short_company_name(r["company_name"]))}</span>')
        density = ' companies-xl' if len(rows) >= 40 else (' companies-lg' if len(rows) >= 24 else (' companies-md' if len(rows) >= 12 else ' companies-sm'))
        return f'<div class="company-row logo-wall{density}" data-count="{len(rows)}">' + ''.join(tags) + '</div>'

    def render_subtree(nid: str, level: int = 0) -> str:
        if nid not in node:
            return ''
        rendered.add(nid)
        cs = children.get(nid, [])
        direct_count = len(companies_by_industry.get(nid, []))
        if not cs:
            if direct_count == 0:
                return ''
            return (
                f'<div class="leaf node-depth-{level}{count_class(direct_count)}" data-id="{esc(nid)}">'
                f'<div class="leaf-title">{esc(node[nid]["name"])}</div>'
                f'{company_tags(nid)}'
                f'</div>'
            )
        direct_html = company_tags(nid) if direct_count else ''
        inner = direct_html + ''.join(render_subtree(c, level + 1) for c in cs)
        if not inner:
            return ''
        return (
            f'<div class="group node-depth-{level}{count_class(subtree_company_count(nid))}" data-id="{esc(nid)}">'
            f'<div class="group-title"><span>{esc(node[nid]["name"])}</span></div>'
            f'<div class="group-body">{inner}</div>'
            f'</div>'
        )

    def render_semiconductor_body(nid: str) -> str:
        """Render semiconductor descendants as independent masonry tiles to avoid large blank areas."""
        tiles = []
        for top in children.get(nid, []):
            rendered.add(top)
            direct = company_tags(top) if companies_by_industry.get(top) else ''
            if direct:
                tiles.append(
                    f'<div class="semi-flat-item" data-parent="{esc(top)}">'
                    f'<div class="semi-parent-label">{esc(node[top]["name"])}</div>{direct}</div>'
                )
            for sub in children.get(top, []):
                sub_html = render_subtree(sub, 2)
                if sub_html:
                    tiles.append(
                        f'<div class="semi-flat-item" data-parent="{esc(top)}">'
                        f'<div class="semi-parent-label">{esc(node[top]["name"])}</div>{sub_html}</div>'
                    )
        return ''.join(tiles)

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
            preferred = ['large_model_industry', 'cloud_service_industry', 'data_center_industry', 'ai_server_industry', 'semiconductor_chip_industry']
            cs = [x for x in preferred if x in cs] + [x for x in cs if x not in preferred]
        cards = []
        for c in cs:
            rendered.add(c)
            extra_cls = (' semiconductor-wide' if nid == 'ai_infrastructure_industry' and c == 'semiconductor_chip_industry' else '') + span_class(c) + count_class(subtree_company_count(c))
            direct_html = company_tags(c) if companies_by_industry.get(c) else ''
            if c == 'semiconductor_chip_industry':
                child_html = render_semiconductor_body(c)
            else:
                child_html = ''.join(render_subtree(gc, 1) for gc in children.get(c, []))
            body = direct_html + child_html
            if not body:
                body = company_tags(c)
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
    preferred_top = ['ai_application_industry', 'ai_terminal_industry', 'ai_infrastructure_industry']
    top_children = [x for x in preferred_top if x in top_children] + [x for x in top_children if x not in preferred_top]

    stages_html = '<div class="landscape-stack">' + ''.join(render_stage(t) for t in top_children) + '</div>'

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
:root{--bg:#F5F6FF;--ink:#20232B;--muted:#858A99;--app:#923BE3;--terminal:#3B54E3;--infra:#3BC4E3;--server:#E33B54;--model:#E3923B;--data:#3BC4E3;--semi:#3B54E3;--cloud:#923BE3;--line:#E7E8EB;--card:#FFFFFF;--tag:#F3F3F4;--brand-soft:#E3E5FF;--app-soft:#F5EEFB;--infra-soft:#EFFAFC;--server-soft:#FDF1F3;--model-soft:#FCF4ED}
*{box-sizing:border-box}html,body{margin:0;background:var(--bg);color:var(--ink);font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Microsoft YaHei",Arial,sans-serif}.zoom-wrap{zoom:.5;width:max-content}.page{width:3840px;margin:0 auto;padding:28px 42px 34px;background:linear-gradient(180deg,#F5F6FF 0%,#FFFFFF 100%)}
.top{display:grid;grid-template-columns:1fr 1.35fr 1fr;gap:20px;align-items:start;margin-bottom:16px}.brand{font-size:28px;font-weight:900;color:#20232B;letter-spacing:.01em}.title{text-align:center}.title h1{margin:0;font-size:52px;line-height:1.02;font-weight:950;letter-spacing:.03em;color:#20232B}.title p{margin:8px 0 0;font-size:16px;color:#858A99;font-weight:700}.meta{text-align:right;font-size:16px;line-height:1.45;color:#535D6D;font-weight:850}.legend{display:flex;align-items:center;justify-content:center;gap:14px;margin:0 0 18px;color:#535D6D;font-weight:900}.legend span{display:inline-flex;align-items:center;border:2px solid currentColor;background:#FFFFFF;border-radius:999px;padding:7px 16px;font-size:16px}.legend span:nth-child(1){color:var(--app)}.legend span:nth-child(3){color:var(--terminal)}.legend span:nth-child(5){color:var(--infra)}.legend b{font-size:18px;color:#adb4ca}
.landscape-stack{display:block}
.stage{--accent:var(--app);position:relative;border:4px solid var(--accent);border-radius:12px;background:rgba(255,255,255,.74);padding:16px 16px 16px;margin-bottom:24px;box-shadow:0 2px 0 color-mix(in srgb,var(--accent) 18%,transparent);overflow:visible}.stage.application{--accent:var(--app)}.stage.terminal{--accent:var(--terminal)}.stage.infra{--accent:var(--infra)}.stage.appendix{--accent:#64748b}.stage-head{position:relative;display:flex;align-items:center;justify-content:space-between;margin:-31px 0 12px;padding:0 12px;pointer-events:none}.stage-head h2{margin:0;background:var(--bg);padding:0 12px;font-size:28px;line-height:1.16;color:var(--accent);font-weight:950;letter-spacing:.02em}.stage-head p{margin:0;background:var(--bg);padding:3px 10px;border-radius:999px;color:#858A99;font-size:15px;font-weight:850}.stage.application .stage-head h2::after{content:"  APPLICATIONS"}.stage.terminal .stage-head h2::after{content:"  TERMINALS"}.stage.infra .stage-head h2::after{content:"  INFRASTRUCTURE"}
.stage::after{position:absolute;right:20px;top:11px;color:#858A99;font-size:15px;font-weight:800}.stage.application::after{content:"应用层：靠近最终业务价值，可按行业/场景紧凑排布"}.stage.terminal::after{content:"终端层：承接模型和硬件能力"}.stage.infra::after{content:"基础设施层：算力、模型、云和芯片供给"}
.major-grid{column-gap:12px;column-fill:balance}.stage.application .major-grid{column-count:8}.stage.terminal .major-grid{column-count:2}.stage.infra .major-grid{column-count:3}.stage.appendix .major-grid{column-count:6}.major-grid.packed{display:grid;grid-template-columns:repeat(var(--masonry-cols),minmax(0,1fr));gap:12px;align-items:start;column-count:auto;column-gap:normal}.masonry-col{min-width:0;display:flex;flex-direction:column;gap:12px}.major-grid.packed .major-card{display:block;margin:0}.major-grid.packed>.major-card[data-id="semiconductor_chip_industry"]{grid-column:1/-1}.major-body.body-packed{display:grid;grid-template-columns:repeat(var(--body-cols),minmax(0,1fr));gap:7px;align-items:start}.major-body.body-packed>.company-row{grid-column:1/-1}.body-masonry-col{min-width:0;display:flex;flex-direction:column;gap:7px}.major-body.body-packed>.body-masonry-col>.group,.major-body.body-packed>.body-masonry-col>.leaf{margin:0}.major-body.semi-body-layout{grid-template-columns:repeat(var(--body-cols),minmax(0,1fr));align-items:start}.major-body.semi-body-layout>.body-masonry-col{gap:7px}.group-body.nested-packed{display:grid;grid-template-columns:repeat(var(--nested-cols),minmax(0,1fr));gap:6px;align-items:start}.nested-masonry-col{min-width:0;display:flex;flex-direction:column;gap:6px}.group-body.nested-packed>.nested-masonry-col>.group,.group-body.nested-packed>.nested-masonry-col>.leaf{margin:0}.semi-flat-item{min-width:0;margin:0;padding:5px;border:1px solid color-mix(in srgb,var(--accent) 34%,#FFFFFF);border-radius:7px;background:rgba(255,255,255,.55);break-inside:avoid}.semi-flat-item>.group,.semi-flat-item>.leaf{margin:0}.semi-parent-label{display:inline-flex;margin:0 0 5px;padding:2px 7px;border-radius:999px;background:color-mix(in srgb,var(--accent) 9%,#fff);color:color-mix(in srgb,var(--accent) 78%,#586078);font-size:10px;line-height:1.1;font-weight:950}.layout-stretched{display:flex;flex-direction:column}.layout-stretched>.group-body,.layout-stretched>.group-body>.leaf,.layout-stretched>.group-body>.group{flex:1;display:flex;flex-direction:column}.layout-stretched .company-row.logo-wall{flex:1;align-content:space-evenly}.major-card.layout-stretched{display:flex;flex-direction:column}.major-card.layout-stretched>.major-body{flex:1;display:flex;flex-direction:column}.major-card.layout-stretched>.major-body>.company-row{flex:1;align-content:space-evenly}.major-card{display:inline-block;width:100%;vertical-align:top;background:rgba(255,255,255,.94);border:2px solid var(--accent);border-radius:8px;padding:8px;margin:0 0 12px;min-width:0;overflow:hidden;break-inside:avoid;page-break-inside:avoid}.major-card>h3{display:flex;align-items:center;justify-content:space-between;margin:0 0 7px;color:var(--accent);font-size:17px;line-height:1.12;font-weight:950;border-bottom:1px solid color-mix(in srgb,var(--accent) 42%,#FFFFFF);padding-bottom:5px}.major-card>h3:after{content:attr(data-count);font-size:10px;color:#A2A6B1}.major-body{min-width:0}.stage.infra .major-card[data-id="large_model_industry"]{--accent:var(--model);min-height:470px}.stage.infra .major-card[data-id="ai_server_industry"]{min-height:470px}.stage.infra .major-card[data-id="cloud_service_industry"]{--accent:var(--cloud)}.stage.infra .major-card[data-id="data_center_industry"]{--accent:var(--data)}.stage.infra .major-card[data-id="ai_server_industry"]{--accent:var(--server)}.stage.infra .major-card[data-id="semiconductor_chip_industry"]{--accent:var(--semi)}.stage.infra .major-card[data-id="ai_server_industry"]>.major-body{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:7px;align-items:start}.stage.infra .major-card[data-id="semiconductor_chip_industry"]>.major-body{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:7px;align-items:start}.stage.infra .major-card[data-id="large_model_industry"]>.major-body,.stage.infra .major-card[data-id="cloud_service_industry"]>.major-body,.stage.infra .major-card[data-id="data_center_industry"]>.major-body{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:7px;align-items:start}.stage.infra .major-card[data-id="large_model_industry"] .body-masonry-col,.stage.infra .major-card[data-id="ai_server_industry"] .body-masonry-col{gap:14px}.stage.infra .major-card[data-id="large_model_industry"] .group,.stage.infra .major-card[data-id="large_model_industry"] .leaf,.stage.infra .major-card[data-id="ai_server_industry"] .group,.stage.infra .major-card[data-id="ai_server_industry"] .leaf{padding:9px}.stage.infra .major-card[data-id="large_model_industry"] .company-row,.stage.infra .major-card[data-id="ai_server_industry"] .company-row{gap:7px}.stage.infra .major-card[data-id="large_model_industry"] .company-tag,.stage.infra .major-card[data-id="ai_server_industry"] .company-tag{height:var(--tag-h);min-height:var(--tag-h)}
.group,.leaf{min-width:0;border:1px solid color-mix(in srgb,var(--accent) 46%,#FFFFFF);background:#fcfdff;border-radius:6px;padding:6px;margin:0 0 6px;overflow:hidden}.major-body>.group:last-child,.major-body>.leaf:last-child{margin-bottom:0}.stage.infra .major-body>.group,.stage.infra .major-body>.leaf{margin:0}.group-title,.leaf-title{font-size:12px;font-weight:950;color:color-mix(in srgb,var(--accent) 72%,#1f2545);line-height:1.12;border-bottom:1px solid color-mix(in srgb,var(--accent) 30%,#FFFFFF);margin-bottom:5px;padding-bottom:4px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.leaf-title{border-bottom:0;margin-bottom:4px;padding-bottom:0}.group-body{min-width:0}.node-depth-2 .group-title,.node-depth-2 .leaf-title,.node-depth-3 .group-title,.node-depth-3 .leaf-title{font-size:10.5px;color:#535D6D}.node-depth-4 .group-title,.node-depth-4 .leaf-title{font-size:10px}.leaf.count-empty{display:none}.company-row.empty{display:none}
.company-row.logo-wall{--company-gap-x:6px;--company-gap-y:6px;--tag-w:84px;--tag-h:22px;position:relative;display:flex;flex-wrap:wrap;gap:var(--company-gap-y) var(--company-gap-x);align-items:stretch;align-content:flex-start;justify-content:space-evenly}.company-row.logo-wall[data-count]::before{content:attr(data-count) "家";position:absolute;right:1px;top:-20px;font-size:10px;color:#A2A6B1;font-weight:850}.company-row.companies-sm,.company-row.companies-md,.company-row.companies-lg,.company-row.companies-xl{--tag-w:84px;--tag-h:22px}.group .company-row,.leaf .company-row{--tag-w:84px;--tag-h:22px;--company-gap-x:5px;--company-gap-y:5px}.company-tag{display:flex;align-items:center;justify-content:center;text-align:center;width:var(--tag-w);height:var(--tag-h);min-width:var(--tag-w);max-width:var(--tag-w);min-height:var(--tag-h);border:1px solid color-mix(in srgb,currentColor 38%,#FFFFFF);background:#F3F3F4;border-radius:6px;padding:2px 5px;line-height:1.06;font-size:10.5px;color:#535D6D;font-weight:900;overflow:hidden;white-space:nowrap;text-overflow:ellipsis;flex:0 0 var(--tag-w)}.company-row.logo-wall.company-cloud .company-tag{flex:0 0 var(--tag-w)}.companies-lg .company-tag,.companies-xl .company-tag,.group .company-tag,.leaf .company-tag{font-size:10.5px;height:var(--tag-h);min-height:var(--tag-h);padding:2px 5px}.market-foreign{background:#E3E5FF;color:#3B54E3;border-color:#3B54E3}.market-hk{background:#EFFAFC;color:#3BC4E3;border-color:#3BC4E3}.market-tw{background:#FCF4ED;color:#E3923B;border-color:#E3923B}.market-growth{background:#F5EEFB;color:#923BE3;border-color:#923BE3}.market-a{background:#F3F3F4;color:#535D6D;border-color:#A2A6B1}.footer{display:flex;justify-content:space-between;border-top:2px solid #3B54E3;margin-top:16px;padding-top:10px;color:#535D6D;font-size:16px;font-weight:800}.auth-overlay{position:fixed;inset:0;z-index:9999;display:flex;align-items:center;justify-content:center;background:linear-gradient(135deg,#F5F6FF,#E3E5FF);padding:20px}.auth-card{width:min(380px,100%);background:#FFFFFF;border:2px solid var(--terminal);border-radius:18px;box-shadow:0 18px 50px rgba(32,35,43,.16);padding:24px}.auth-card h2{margin:0 0 6px;color:#20232B;font-size:24px}.auth-card p{margin:0 0 18px;color:var(--muted);font-size:13px}.auth-card label{display:block;margin:12px 0 6px;font-weight:850;color:#20232B}.auth-card input{width:100%;height:40px;border:1px solid #3B54E3;border-radius:10px;padding:0 12px;font-size:15px}.auth-card button{width:100%;height:42px;margin-top:18px;border:0;border-radius:10px;background:var(--terminal);color:#fff;font-weight:950;cursor:pointer}.auth-error{min-height:20px;margin-top:10px;color:#E33B54;font-size:13px;font-weight:800}.auth-hidden{display:none!important}body.auth-locked .zoom-wrap{display:none}@media(max-width:1200px){.zoom-wrap{zoom:.42}.page{width:3840px}}
'''

    html_text = f'''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"/><meta name="viewport" content="width=device-width,initial-scale=1"/><title>AI产业链全景图谱</title><style>{css}</style></head><body class="auth-locked"><div class="auth-overlay" id="authOverlay"><form class="auth-card" id="authForm"><h2>访问验证</h2><p>请输入用户名和密码查看 AI 产业链全景图谱。</p><label for="authUser">用户名</label><input id="authUser" name="username" autocomplete="username" autofocus/><label for="authPass">密码</label><input id="authPass" name="password" type="password" autocomplete="current-password"/><button type="submit">登录</button><div class="auth-error" id="authError"></div></form></div><div class="zoom-wrap" id="zoomWrap"><main class="page"><header class="top"><div class="brand">AI产业链 Graph</div><div class="title"><h1>AI产业链全景图谱</h1><p>由 nodes.csv、edges.csv、company_nodes.csv、industry_company_edges.csv 生成</p></div><div class="meta">产业节点 {len(nodes)}<br/>公司节点 {len(company_nodes)}<br/>产业-公司关系 {total_company_edges}</div></header><div class="legend"><span>下游应用</span><b>·</b><span>中游智能终端</span><b>·</b><span>上游基础设施</span></div>{stages_html}{appendix}<div class="footer"><span>大框表示产业层级分区，内部小框表示下级产业；公司简称方块替代 logo，位置越上方越接近下游应用。</span><span>生成时间：{esc(generated)}</span></div></main></div><script>const __AUTH_USER={AUTH_USERNAME!r};const __AUTH_PASS={AUTH_PASSWORD!r};const __AUTH_KEY="ai_atlas_auth_ok";const __authOverlay=document.getElementById("authOverlay");const __authForm=document.getElementById("authForm");const __authError=document.getElementById("authError");function __packMasonry(){{
  const countFor=(grid)=>{{
    const stage=grid.closest(".stage");
    if(!stage) return 4;
    if(stage.classList.contains("application")) return 8;
    if(stage.classList.contains("terminal")) return 2;
    if(stage.classList.contains("infra")) return 3;
    return 6;
  }};
  document.querySelectorAll(".major-grid").forEach((grid)=>{{
    if(grid.dataset.packed==="1") return;
    const allCards=[...grid.children].filter(el=>el.classList&&el.classList.contains("major-card"));
    if(!allCards.length) return;
    const stage=grid.closest(".stage");
    const bottomCards=(stage&&stage.classList.contains("infra"))?allCards.filter(card=>card.dataset.id==="semiconductor_chip_industry"):[];
    const cards=allCards.filter(card=>!bottomCards.includes(card));
    const n=Math.max(1,Math.min(countFor(grid),cards.length||allCards.length));
    grid.dataset.packed="1";
    grid.classList.add("packed");
    grid.style.setProperty("--masonry-cols",n);
    const cols=Array.from({{length:n}},()=>{{const c=document.createElement("div");c.className="masonry-col";grid.appendChild(c);return c;}});
    cards.sort((a,b)=>b.getBoundingClientRect().height-a.getBoundingClientRect().height).forEach(card=>{{
      const target=cols.reduce((a,b)=>a.scrollHeight<=b.scrollHeight?a:b);
      target.appendChild(card);
    }});
    bottomCards.forEach(card=>grid.appendChild(card));
  }});
  document.querySelectorAll(".major-body").forEach((body)=>{{
    if(body.dataset.bodyPacked==="1") return;
    const items=[...body.children].filter(el=>el.classList&&(el.classList.contains("group")||el.classList.contains("leaf")||el.classList.contains("semi-flat-item")));
    if(items.length<4) return;
    const card=body.closest(".major-card");
    const stage=body.closest(".stage");
    if(card&&card.dataset.id==="semiconductor_chip_industry"){{
      body.dataset.bodyPacked="1";
      body.classList.add("body-packed","semi-body-layout");
      const n=Math.max(3,Math.min(5,Math.round((body.getBoundingClientRect().width||1200)/310),items.length));
      body.style.setProperty("--body-cols",n);
      const cols=Array.from({{length:n}},()=>{{
        const c=document.createElement("div");
        c.className="body-masonry-col semi-masonry-col";
        body.appendChild(c);
        return c;
      }});
      items.sort((a,b)=>b.getBoundingClientRect().height-a.getBoundingClientRect().height).forEach(item=>{{
        const target=cols.reduce((a,b)=>a.scrollHeight<=b.scrollHeight?a:b);
        target.appendChild(item);
      }});
      requestAnimationFrame(()=>__packNestedSemiconductorGroups(card));
      return;
    }}
    let n=2;
    if(stage&&stage.classList.contains("infra")&&items.length>=8) n=3;
    if(card&&card.getBoundingClientRect().width<420) n=2;
    n=Math.min(n,items.length);
    body.dataset.bodyPacked="1";
    body.classList.add("body-packed");
    body.style.setProperty("--body-cols",n);
    const cols=Array.from({{length:n}},()=>{{const c=document.createElement("div");c.className="body-masonry-col";body.appendChild(c);return c;}});
    items.sort((a,b)=>b.getBoundingClientRect().height-a.getBoundingClientRect().height).forEach(item=>{{
      const target=cols.reduce((a,b)=>a.scrollHeight<=b.scrollHeight?a:b);
      target.appendChild(item);
    }});
  }});
  __stretchAlignedBlocks();
  __alignIndustryCardGroups();
  __relaxCompanyRows();
  requestAnimationFrame(()=>{{__stretchAlignedBlocks();__alignIndustryCardGroups();__relaxCompanyRows();}});
}}
function __alignIndustryCardGroups(){{
  const groups=[
    ["education_ai_industry","chemical_ai_industry","basic_materials_ai_industry"],
    ["industrial_ai_industry","healthcare_ai_industry","ai_marketing_sales_industry","ai_supply_chain_management_industry"],
    ["ai_decision_intelligence_industry","high_tech_ai_industry","enterprise_office_software_industry","ai_hr_software_industry","electronics_ai_industry"]
  ];
  groups.forEach(ids=>{{
    const cards=ids.map(id=>document.querySelector(`.stage.application .major-card[data-id="${{id}}"]`)).filter(Boolean);
    if(cards.length<2) return;
    cards.forEach(card=>{{card.style.minHeight="";card.classList.remove("layout-stretched");}});
    const rects=cards.map(card=>card.getBoundingClientRect());
    const maxBottom=Math.max(...rects.map(r=>r.bottom));
    cards.forEach((card,i)=>{{
      const rect=rects[i];
      const deficit=maxBottom-rect.bottom;
      if(deficit>4){{
        card.style.minHeight=Math.ceil(rect.height+deficit)+"px";
        card.classList.add("layout-stretched");
      }}
    }});
  }});
}}
function __stretchAlignedBlocks(){{
  const configs=[{{
    cardId:"intelligent_driving_industry",
    stretchIds:["intelligent_driving_software_industry","intelligent_driving_communication_industry","intelligent_driving_actuation_industry"]
  }}];
  configs.forEach(cfg=>{{
    const card=document.querySelector(`.major-card[data-id="${{cfg.cardId}}"]`);
    if(!card) return;
    const cols=[...card.querySelectorAll(":scope > .major-body.body-packed > .body-masonry-col")];
    if(cols.length<2) return;
    const targets=cfg.stretchIds.map(id=>card.querySelector(`[data-id="${{id}}"]`)).filter(Boolean);
    targets.forEach(el=>{{el.style.minHeight="";el.classList.remove("layout-stretched");}});
    const maxH=Math.max(...cols.map(c=>c.scrollHeight));
    cols.forEach(col=>{{
      const deficit=maxH-col.scrollHeight;
      if(deficit<=6) return;
      const stretchables=cfg.stretchIds.map(id=>col.querySelector(`[data-id="${{id}}"]`)).filter(Boolean);
      if(!stretchables.length) return;
      const add=deficit/stretchables.length;
      stretchables.forEach(el=>{{
        const h=el.getBoundingClientRect().height;
        el.style.minHeight=Math.ceil(h+add)+"px";
        el.classList.add("layout-stretched");
      }});
    }});
  }});
}}
function __packNestedSemiconductorGroups(card){{
  card.querySelectorAll(".group > .group-body").forEach((gb)=>{{
    if(gb.dataset.nestedPacked==="1") return;
    const items=[...gb.children].filter(el=>el.classList&&(el.classList.contains("group")||el.classList.contains("leaf")));
    if(items.length<4) return;
    const w=gb.getBoundingClientRect().width||gb.clientWidth||240;
    let n=1;
    if(w>620&&items.length>=7) n=3;
    else if(w>260) n=2;
    n=Math.min(n,items.length);
    if(n<2) return;
    gb.dataset.nestedPacked="1";
    gb.classList.add("nested-packed");
    gb.style.setProperty("--nested-cols",n);
    const cols=Array.from({{length:n}},()=>{{
      const c=document.createElement("div");
      c.className="nested-masonry-col";
      gb.appendChild(c);
      return c;
    }});
    items.sort((a,b)=>b.getBoundingClientRect().height-a.getBoundingClientRect().height).forEach(item=>{{
      const target=cols.reduce((a,b)=>a.scrollHeight<=b.scrollHeight?a:b);
      target.appendChild(item);
    }});
  }});
  __relaxCompanyRows();
}}
function __relaxCompanyRows(){{
  document.querySelectorAll(".company-row.logo-wall").forEach((row)=>{{
    const tags=[...row.querySelectorAll(".company-tag")];
    if(!tags.length) return;
    const w=row.getBoundingClientRect().width||row.clientWidth||320;
    const tileW=84;
    const targetCols=Math.max(1,Math.min(tags.length,Math.floor(w/tileW)||1));
    const slack=Math.max(0,w-targetCols*tileW);
    const gapX=Math.max(4,Math.min(18,slack/Math.max(1,targetCols-1)));
    const gapY=Math.max(4,Math.min(12,gapX*.65+1));
    row.classList.add("company-cloud");
    row.style.setProperty("--tag-w",tileW+"px");
    row.style.setProperty("--tag-h","22px");
    row.style.setProperty("--company-gap-x",gapX.toFixed(1)+"px");
    row.style.setProperty("--company-gap-y",gapY.toFixed(1)+"px");
    tags.forEach((tag)=>{{
      tag.style.removeProperty("--tag-flex-basis");
      tag.style.removeProperty("--tag-flex-grow");
    }});
  }});
}}
function __unlock(){{document.body.classList.remove("auth-locked");__authOverlay.classList.add("auth-hidden");requestAnimationFrame(__packMasonry);}}if(sessionStorage.getItem(__AUTH_KEY)==="1"){{__unlock();}}__authForm.addEventListener("submit",(e)=>{{e.preventDefault();const u=document.getElementById("authUser").value.trim();const p=document.getElementById("authPass").value;if(u===__AUTH_USER&&p===__AUTH_PASS){{sessionStorage.setItem(__AUTH_KEY,"1");__unlock();}}else{{__authError.textContent="用户名或密码错误";document.getElementById("authPass").value="";document.getElementById("authPass").focus();}}}});</script></body></html>'''
    OUT.write_text(html_text, encoding='utf-8')
    print(f'wrote {OUT} from 4 CSV files: industry_nodes={len(nodes)}, industry_edges={len(edges)}, companies={len(company_nodes)}, industry_company_edges={len(industry_company_edges)}')

if __name__ == '__main__':
    main()
