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
:root{--bg:#fafafe;--ink:#22223b;--muted:#7b819a;--app:#c026d3;--terminal:#4f5bd5;--infra:#2a9d84;--server:#ff4d4f;--model:#f59e2e;--data:#24b6d5;--semi:#2f8fbd;--cloud:#7657d9;--line:#d9def0;--card:#fff;--tag:#f8f9fd}
*{box-sizing:border-box}html,body{margin:0;background:var(--bg);color:var(--ink);font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Microsoft YaHei",Arial,sans-serif}.zoom-wrap{zoom:.5;width:max-content}.page{width:3840px;margin:0 auto;padding:34px 54px 42px;background:linear-gradient(180deg,#fbfbff 0%,#f7fbff 100%)}
.top{display:grid;grid-template-columns:1fr 1.35fr 1fr;gap:24px;align-items:start;margin-bottom:22px}.brand{font-size:30px;font-weight:900;color:#30314f;letter-spacing:.01em}.title{text-align:center}.title h1{margin:0;font-size:56px;line-height:1.04;font-weight:950;letter-spacing:.03em;color:#272945}.title p{margin:10px 0 0;font-size:17px;color:#7b819a;font-weight:700}.meta{text-align:right;font-size:17px;line-height:1.55;color:#596080;font-weight:850}.legend{display:flex;align-items:center;justify-content:center;gap:18px;margin:0 0 24px;color:#5d6380;font-weight:900}.legend span{display:inline-flex;align-items:center;border:2px solid currentColor;background:#fff;border-radius:999px;padding:8px 18px;font-size:17px}.legend span:nth-child(1){color:var(--app)}.legend span:nth-child(3){color:var(--terminal)}.legend span:nth-child(5){color:var(--infra)}.legend b{font-size:20px;color:#adb4ca}
.stage{--accent:var(--app);position:relative;border:4px solid var(--accent);border-radius:14px;background:rgba(255,255,255,.72);padding:18px 20px 20px;margin-bottom:30px;box-shadow:0 1px 0 rgba(38,41,69,.05);overflow:visible}.stage.application{--accent:var(--app)}.stage.terminal{--accent:var(--terminal)}.stage.infra{--accent:var(--infra)}.stage.appendix{--accent:#64748b}.stage-head{position:relative;display:flex;align-items:center;justify-content:space-between;margin:-33px 0 14px;padding:0 16px;pointer-events:none}.stage-head h2{margin:0;background:var(--bg);padding:0 14px;font-size:31px;line-height:1.2;color:var(--accent);font-weight:950;letter-spacing:.02em}.stage-head p{margin:0;background:var(--bg);padding:4px 12px;border-radius:999px;color:#7b819a;font-size:17px;font-weight:850}.stage-head h2:after{content:"  " attr(data-en)}
.stage.application .stage-head h2::after{content:"  APPLICATIONS"}.stage.terminal .stage-head h2::after{content:"  TERMINALS"}.stage.infra .stage-head h2::after{content:"  INFRASTRUCTURE"}
.stage::after{position:absolute;right:24px;top:13px;color:#878da6;font-size:17px;font-weight:800}.stage.application::after{content:"AI进入行业与企业工作流：越靠上越接近最终应用 / 业务价值"}.stage.terminal::after{content:"AI手机 / AIPC / 智能驾驶 / 人形机器人 / AI眼镜承接模型与硬件能力"}.stage.infra::after{content:"芯片、服务器、数据中心、云与大模型向上游供给算力和模型能力"}
.major-grid{display:grid;gap:14px;align-items:stretch}.stage.application .major-grid{grid-template-columns:repeat(6,minmax(0,1fr))}.stage.terminal .major-grid{grid-template-columns:repeat(5,minmax(0,1fr))}.stage.infra .major-grid{grid-template-columns:repeat(3,minmax(0,1fr));gap:16px}.stage.appendix .major-grid{grid-template-columns:repeat(6,minmax(0,1fr))}
.major-card{background:rgba(255,255,255,.92);border:2px solid var(--accent);border-radius:9px;padding:10px;min-width:0;overflow:hidden}.stage.application .major-card{min-height:122px}.stage.terminal .major-card{min-height:372px}.major-card>h3{display:flex;align-items:center;justify-content:space-between;margin:0 0 8px;color:var(--accent);font-size:18px;line-height:1.15;font-weight:950;border-bottom:1px solid color-mix(in srgb,var(--accent) 22%,#fff);padding-bottom:6px}.major-card>h3:after{content:attr(data-count);font-size:11px;color:#9aa1b7}.major-body{min-width:0}.stage.infra .major-card[data-id="large_model_industry"]{--accent:var(--model);order:1;min-height:178px}.stage.infra .major-card[data-id="cloud_service_industry"]{--accent:var(--cloud);order:2;min-height:178px}.stage.infra .major-card[data-id="data_center_industry"]{--accent:var(--data);order:3;min-height:178px}.stage.infra .major-card[data-id="ai_server_industry"]{--accent:var(--server);order:4;grid-column:1/-1;min-height:288px}.stage.infra .major-card[data-id="semiconductor_chip_industry"]{--accent:var(--semi);order:5;grid-column:1/-1;min-height:310px}.stage.infra .major-card[data-id="ai_server_industry"]>.major-body{display:grid;grid-template-columns:repeat(6,minmax(0,1fr));gap:10px}.stage.infra .major-card[data-id="semiconductor_chip_industry"]>.major-body{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:10px}.stage.infra .major-card[data-id="large_model_industry"]>.major-body{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:8px}.stage.infra .major-card[data-id="cloud_service_industry"]>.major-body{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px}.stage.infra .major-card[data-id="data_center_industry"]>.major-body{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:8px}
.group,.leaf{min-width:0;border:1px solid color-mix(in srgb,var(--accent) 28%,#dfe4f2);background:#fcfdff;border-radius:7px;padding:7px;margin:0 0 7px;overflow:hidden}.stage.terminal .group,.stage.terminal .leaf{margin-bottom:8px}.major-card>.major-body>.group:last-child,.major-card>.major-body>.leaf:last-child{margin-bottom:0}.group-title,.leaf-title{font-size:13px;font-weight:950;color:color-mix(in srgb,var(--accent) 72%,#1f2545);line-height:1.15;border-bottom:1px solid #e8ebf4;margin-bottom:6px;padding-bottom:4px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.leaf-title{border-bottom:0;margin-bottom:5px;padding-bottom:0}.group-body{min-width:0}.stage.infra .major-card[data-id="ai_server_industry"] .group,.stage.infra .major-card[data-id="ai_server_industry"] .leaf{margin:0;min-height:92px}.stage.infra .major-card[data-id="semiconductor_chip_industry"] .group{margin:0;min-height:246px}.stage.infra .major-card[data-id="large_model_industry"] .group,.stage.infra .major-card[data-id="cloud_service_industry"] .group,.stage.infra .major-card[data-id="data_center_industry"] .group{margin:0;min-height:104px}.node-depth-2 .group-title,.node-depth-2 .leaf-title,.node-depth-3 .group-title,.node-depth-3 .leaf-title{font-size:11px;color:#68708f}.node-depth-4 .group-title,.node-depth-4 .leaf-title{font-size:10px}.leaf.count-empty{display:none}.company-row.empty{display:none}
.company-row.logo-wall{position:relative;display:grid;grid-template-columns:repeat(auto-fill,minmax(92px,1fr));gap:6px;align-items:stretch}.company-row.logo-wall:after{content:"";display:block;clear:both}.company-row.logo-wall[data-count]::before{content:attr(data-count) "家";position:absolute;right:2px;top:-23px;font-size:11px;color:#9ba2b8;font-weight:850}.company-row.companies-sm{grid-template-columns:repeat(auto-fit,minmax(116px,1fr))}.company-row.companies-md{grid-template-columns:repeat(auto-fill,minmax(102px,1fr))}.company-row.companies-lg{grid-template-columns:repeat(auto-fill,minmax(92px,1fr))}.company-row.companies-xl{grid-template-columns:repeat(auto-fill,minmax(82px,1fr));gap:5px}.company-tag{display:flex;align-items:center;justify-content:center;text-align:center;min-height:26px;border:1px solid #dde2f0;background:#f8f9fd;border-radius:7px;padding:3px 6px;line-height:1.08;max-width:100%;font-size:12px;color:#46506f;font-weight:900;overflow:hidden;white-space:nowrap;text-overflow:ellipsis}.companies-lg .company-tag{font-size:11px;min-height:24px}.companies-xl .company-tag{font-size:10.5px;min-height:22px;padding:2px 4px}.group .company-row{grid-template-columns:repeat(auto-fill,minmax(78px,1fr));gap:5px}.group .company-tag,.leaf .company-tag{min-height:22px;font-size:10.5px}.market-foreign{background:#f7f7ff;color:#4148aa;border-color:#e0e3ff}.market-hk{background:#f3fcff;color:#1b869f;border-color:#d5f0f6}.market-tw{background:#fff8ed;color:#af650e;border-color:#f4dfbc}.market-growth{background:#fcf5ff;color:#9846b0;border-color:#eed9f5}.market-a{background:#f8f9fd;color:#46506f;border-color:#dde2f0}.footer{display:flex;justify-content:space-between;border-top:2px solid #e0e5f2;margin-top:18px;padding-top:12px;color:#65708f;font-size:17px;font-weight:800}.auth-overlay{position:fixed;inset:0;z-index:9999;display:flex;align-items:center;justify-content:center;background:linear-gradient(135deg,#fbfbff,#eef3ff);padding:20px}.auth-card{width:min(380px,100%);background:#fff;border:2px solid var(--terminal);border-radius:18px;box-shadow:0 18px 50px rgba(33,44,100,.18);padding:24px}.auth-card h2{margin:0 0 6px;color:#252a60;font-size:24px}.auth-card p{margin:0 0 18px;color:var(--muted);font-size:13px}.auth-card label{display:block;margin:12px 0 6px;font-weight:850;color:#252a60}.auth-card input{width:100%;height:40px;border:1px solid #d7ddfc;border-radius:10px;padding:0 12px;font-size:15px}.auth-card button{width:100%;height:42px;margin-top:18px;border:0;border-radius:10px;background:var(--terminal);color:#fff;font-weight:950;cursor:pointer}.auth-error{min-height:20px;margin-top:10px;color:#dc2626;font-size:13px;font-weight:800}.auth-hidden{display:none!important}body.auth-locked .zoom-wrap{display:none}@media(max-width:1200px){.zoom-wrap{zoom:.42}.page{width:3840px}}
'''

    html_text = f'''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"/><meta name="viewport" content="width=device-width,initial-scale=1"/><title>AI产业链全景图谱</title><style>{css}</style></head><body class="auth-locked"><div class="auth-overlay" id="authOverlay"><form class="auth-card" id="authForm"><h2>访问验证</h2><p>请输入用户名和密码查看 AI 产业链全景图谱。</p><label for="authUser">用户名</label><input id="authUser" name="username" autocomplete="username" autofocus/><label for="authPass">密码</label><input id="authPass" name="password" type="password" autocomplete="current-password"/><button type="submit">登录</button><div class="auth-error" id="authError"></div></form></div><div class="zoom-wrap" id="zoomWrap"><main class="page"><header class="top"><div class="brand">AI产业链 Graph</div><div class="title"><h1>AI产业链全景图谱</h1><p>由 nodes.csv、edges.csv、company_nodes.csv、industry_company_edges.csv 生成</p></div><div class="meta">产业节点 {len(nodes)}<br/>公司节点 {len(company_nodes)}<br/>产业-公司关系 {total_company_edges}</div></header><div class="legend"><span>下游应用</span><b>·</b><span>中游智能终端</span><b>·</b><span>上游基础设施</span></div>{stages_html}{appendix}<div class="footer"><span>大框表示产业层级分区，内部小框表示下级产业；公司简称方块替代 logo，位置越上方越接近下游应用。</span><span>生成时间：{esc(generated)}</span></div></main></div><script>const __AUTH_USER={AUTH_USERNAME!r};const __AUTH_PASS={AUTH_PASSWORD!r};const __AUTH_KEY="ai_atlas_auth_ok";const __authOverlay=document.getElementById("authOverlay");const __authForm=document.getElementById("authForm");const __authError=document.getElementById("authError");function __packMasonry(){{
  // CSS Grid now controls the fixed landscape layout; reserved for future interactions.
}}
function __unlock(){{document.body.classList.remove("auth-locked");__authOverlay.classList.add("auth-hidden");requestAnimationFrame(__packMasonry);}}if(sessionStorage.getItem(__AUTH_KEY)==="1"){{__unlock();}}__authForm.addEventListener("submit",(e)=>{{e.preventDefault();const u=document.getElementById("authUser").value.trim();const p=document.getElementById("authPass").value;if(u===__AUTH_USER&&p===__AUTH_PASS){{sessionStorage.setItem(__AUTH_KEY,"1");__unlock();}}else{{__authError.textContent="用户名或密码错误";document.getElementById("authPass").value="";document.getElementById("authPass").focus();}}}});</script></body></html>'''
    OUT.write_text(html_text, encoding='utf-8')
    print(f'wrote {OUT} from 4 CSV files: industry_nodes={len(nodes)}, industry_edges={len(edges)}, companies={len(company_nodes)}, industry_company_edges={len(industry_company_edges)}')

if __name__ == '__main__':
    main()
