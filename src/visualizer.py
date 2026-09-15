# -*- coding: utf-8 -*-
"""
可视化层（day8 风格大屏 + 静态图）
==================================
1. matplotlib：支持度条形图、置信度-提升度散点图、规则热力图（PNG 备查）
2. ECharts day8 大屏：单页 index.html + app.js + 本地化 echarts 库
   4 个 panel 网格布局，带 #status 状态栏，用 fetch 调 Spring Boot 接口
所有文件写入 outputs/charts，可直接用于答辩展示或部署到 Spring Boot static 目录。
"""
import os
import json
import urllib.request
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from config import CHART_DIR, MATPLOT_FONT, TOP_N_RULES


def _set_font():
    try:
        plt.rcParams["font.sans-serif"] = [MATPLOT_FONT]
        plt.rcParams["axes.unicode_minus"] = False
    except Exception:
        pass


# ============ matplotlib 静态图（备份/答辩截图用）============

def plot_top_itemsets(freq_df: pd.DataFrame, top_n: int = 15,
                      out_path: str = None) -> str:
    _set_font()
    df = freq_df.copy()
    df["len"] = df["itemsets"].apply(len)
    df = df[df["len"] >= 2].head(top_n)
    df["label"] = df["itemsets"].apply(lambda s: "{" + ",".join(sorted(s)) + "}")
    out_path = out_path or os.path.join(CHART_DIR, "top_itemsets.png")
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.barh(df["label"][::-1], df["support"][::-1], color="#4C9F70")
    ax.set_xlabel("support（支持度）")
    ax.set_title("Top 频繁项集（长度>=2）")
    for i, v in enumerate(df["support"][::-1]):
        ax.text(v, i, f" {v:.3f}", va="center")
    plt.tight_layout()
    plt.savefig(out_path, dpi=150)
    plt.close()
    return out_path


def plot_rules_scatter(rules: pd.DataFrame, out_path: str = None) -> str:
    _set_font()
    out_path = out_path or os.path.join(CHART_DIR, "rules_scatter.png")
    fig, ax = plt.subplots(figsize=(10, 6))
    if not rules.empty:
        ax.scatter(rules["confidence"], rules["lift"],
                   s=rules["support"] * 2000, alpha=0.6, c="#E8743B")
        ax.axhline(1, color="gray", ls="--", lw=1)
        ax.text(rules["confidence"].max() * 0.98, 1.02, "lift=1（独立）",
                ha="right", color="gray")
    ax.set_xlabel("confidence（置信度）")
    ax.set_ylabel("lift（提升度）")
    ax.set_title("关联规则：置信度 vs 提升度（气泡=支持度）")
    plt.tight_layout()
    plt.savefig(out_path, dpi=150)
    plt.close()
    return out_path


def plot_rules_bar(rules: pd.DataFrame, top_n: int = TOP_N_RULES,
                   out_path: str = None) -> str:
    _set_font()
    out_path = out_path or os.path.join(CHART_DIR, "top_rules.png")
    df = rules.head(top_n).copy()
    if df.empty:
        return out_path
    df["rule"] = df.apply(
        lambda r: "{" + ",".join(sorted(r["antecedents"])) + "}=>{" +
                  ",".join(sorted(r["consequents"])) + "}", axis=1)
    fig, ax = plt.subplots(figsize=(12, 7))
    ax.barh(df["rule"][::-1], df["lift"][::-1], color="#3B7DD8")
    ax.set_xlabel("lift（提升度）")
    ax.set_title("Top 关联规则（按提升度排序）")
    for i, v in enumerate(df["lift"][::-1]):
        ax.text(v, i, f" {v:.2f}", va="center")
    plt.tight_layout()
    plt.savefig(out_path, dpi=150)
    plt.close()
    return out_path


def plot_cooccurrence_heatmap(encoded_df: pd.DataFrame,
                               top_items: int = 12,
                               out_path: str = None) -> str:
    _set_font()
    out_path = out_path or os.path.join(CHART_DIR, "cooccurrence_heatmap.png")
    top = encoded_df.sum().sort_values(ascending=False).head(top_items).index
    sub = encoded_df[top].astype(int)
    co = sub.T.dot(sub)
    fig, ax = plt.subplots(figsize=(10, 8))
    im = ax.imshow(co.values, cmap="YlOrRd")
    ax.set_xticks(range(len(top)))
    ax.set_yticks(range(len(top)))
    ax.set_xticklabels(top, rotation=45, ha="right")
    ax.set_yticklabels(top)
    vmax = co.values.max()
    for i in range(len(top)):
        for j in range(len(top)):
            ax.text(j, i, str(co.values[i, j]), ha="center", va="center",
                    color="black" if co.values[i, j] < vmax / 2 else "white",
                    fontsize=8)
    plt.colorbar(im, ax=ax, label="共现次数")
    ax.set_title("高频项共现热力图")
    plt.tight_layout()
    plt.savefig(out_path, dpi=150)
    plt.close()
    return out_path


# ============ ECharts day8 风格大屏 ============

# 本地化 echarts 库 CDN 地址（首次运行下载到 outputs/charts/js/）
_ECHARTS_URL = "https://cdn.jsdelivr.net/npm/echarts@5.4.3/dist/echarts.min.js"
_WORDCLOUD_URL = "https://cdn.jsdelivr.net/npm/echarts-wordcloud@2.1.0/dist/echarts-wordcloud.min.js"


def _ensure_echarts_libs():
    """下载 echarts.min.js + echarts-wordcloud.min.js 到 charts/js/，已存在跳过。"""
    js_dir = os.path.join(CHART_DIR, "js")
    os.makedirs(js_dir, exist_ok=True)
    targets = {
        "echarts.min.js": _ECHARTS_URL,
        "echarts-wordcloud.min.js": _WORDCLOUD_URL,
    }
    for fname, url in targets.items():
        dst = os.path.join(js_dir, fname)
        if os.path.exists(dst) and os.path.getsize(dst) > 10000:
            continue
        try:
            print(f"  下载 {fname}...")
            urllib.request.urlretrieve(url, dst)
            print(f"    -> {dst}（{os.path.getsize(dst)//1024} KB）")
        except Exception as e:
            print(f"  [警告] 下载 {fname} 失败: {e}（大屏将退回 CDN）")


_INDEX_TPL = """<!DOCTYPE html>
<html lang="zh">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>技能组合关联规则分析大屏</title>
  <script src="js/echarts.min.js"></script>
  <script src="js/echarts-wordcloud.min.js"></script>
  <style>
    body { font-family: "Microsoft YaHei", sans-serif; background: #f4f6f9; margin: 0; padding: 16px; color: #333; }
    h2 { text-align: center; color: #1f3a5f; font-size: 24px; margin: 0 0 4px; }
    #status { text-align: center; color: #666; font-size: 13px; margin: 0 0 12px; }
    .grid { max-width: 1320px; margin: 0 auto; display: grid;
            grid-template-columns: repeat(2, 1fr); gap: 14px; }
    .panel { background: #fff; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,.07);
             padding: 14px; display: flex; flex-direction: column; box-sizing: border-box; min-width: 0; }
    .panel h3 { color: #2c5aa0; border-left: 4px solid #2c5aa0; padding-left: 10px; font-size: 15px; margin: 0 0 6px; }
    .chart { flex: 1; width: 100%; min-height: 380px; }
    .dark { background: #101418; }
    .dark h3 { color: #fff; border-color: #3b82f6; }
    @media (max-width: 900px) { .grid { grid-template-columns: 1fr; } }
  </style>
</head>
<body>
  <h2>技能组合关联规则分析大屏</h2>
  <p id="status">正在从后端接口加载数据…</p>
  <div class="grid">
    <div class="panel"><h3>Top 频繁技能项集</h3><div id="freqChart" class="chart"></div></div>
    <div class="panel"><h3>规则散点（置信度 vs 提升度）</h3><div id="scatterChart" class="chart"></div></div>
    <div class="panel dark"><h3>技能关键词词云</h3><div id="kwChart" class="chart"></div></div>
    <div class="panel"><h3>Top 强规则（按 lift 排序）</h3><div id="ruleChart" class="chart"></div></div>
  </div>
  <script src="app.js"></script>
</body>
</html>
"""

_APP_JS = """'use strict';
var freqEl    = echarts.init(document.getElementById('freqChart'));
var scatterEl = echarts.init(document.getElementById('scatterChart'));
var kwEl      = echarts.init(document.getElementById('kwChart'));
var ruleEl    = echarts.init(document.getElementById('ruleChart'));
var statusEl  = document.getElementById('status');
window.addEventListener('resize', function () {
  [freqEl, scatterEl, kwEl, ruleEl].forEach(function (el) { el && el.resize(); });
});

function drawFreq(list) {
  var top = list.slice(0, 15).reverse();
  freqEl.setOption({
    title: { text: 'Top 频繁项集', left: 'center' },
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' },
               formatter: function (p) { return p[0].name + '<br/>support=' + p[0].value; } },
    grid: { left: '28%', right: '12%', top: 40 },
    xAxis: { type: 'value', name: 'support' },
    yAxis: { type: 'category', data: top.map(function (i) { return i.items; }),
             axisLabel: { fontSize: 11 } },
    series: [{ type: 'bar', data: top.map(function (i) { return i.support; }),
      barWidth: '55%', itemStyle: { color: '#4C9F70' },
      label: { show: true, position: 'right', formatter: function (p) { return p.value.toFixed(3); } } }]
  });
}

function drawScatter(rules) {
  // 修复错位：data 用纯数字数组，rule 存外部 map，避免字符串进 visualMap
  var ruleMap = {};
  var data = rules.map(function (r, i) { ruleMap[i] = r.rule; return [r.confidence, r.lift, r.support, i]; });
  scatterEl.setOption({
    title: { text: '置信度 vs 提升度', left: 'center' },
    tooltip: { trigger: 'item', formatter: function (p) {
      var d = p.data;
      return ruleMap[d[3]] + '<br/>conf=' + d[0].toFixed(3) + '  lift=' + d[1].toFixed(3) + '  support=' + d[2].toFixed(3); } },
    grid: { left: '10%', right: '10%', top: 40, bottom: 50 },
    xAxis: { type: 'value', name: 'confidence', min: 0, max: 1.0, nameLocation: 'middle', nameGap: 28,
             axisLabel: { formatter: function (v) { return v.toFixed(1); } } },
    yAxis: { type: 'value', name: 'lift' },
    // dimension:1 明确按 lift 映射颜色，避免取最后一位(索引)干扰
    visualMap: { min: 1, max: 15, dimension: 1, calculable: true, orient: 'horizontal', left: 'center', bottom: 5,
                 inRange: { color: ['#f5d4d4', '#c23531'] },
                 text: ['lift高', 'lift低'] },
    series: [{ type: 'scatter', data: data,
      symbolSize: function (d) { return Math.max(6, d[2] * 100); }, itemStyle: { opacity: 0.55 } }]
  });
}

function drawKeyword(pairs) {
  var top = pairs.slice().sort(function (a, b) { return b.value - a.value; }).slice(0, 60);
  kwEl.setOption({ series: [{ type: 'wordCloud', shape: 'circle',
    sizeRange: [14, 56], rotationRange: [-45, 45], gridSize: 12, width: '100%', height: '85%', data: top,
    textStyle: { fontFamily: 'Microsoft YaHei',
      color: function () { var c = ['#22d3ee', '#4ade80', '#facc15', '#a78bfa', '#60a5fa', '#f472b6', '#fb923c'];
        return c[Math.floor(Math.random() * c.length)]; } } }] });
}

function drawRules(rules) {
  var top = rules.slice(0, 12).reverse();
  ruleEl.setOption({
    title: { text: 'Top 强规则', left: 'center' },
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' }, formatter: function (p) {
      var i = p[0].dataIndex; return top[top.length - 1 - i].rule + '<br/>lift=' + p[0].value.toFixed(3); } },
    grid: { left: '38%', right: '12%', top: 40 },
    xAxis: { type: 'value', name: 'lift' },
    yAxis: { type: 'category', data: top.map(function (r) { return r.rule; }), axisLabel: { fontSize: 11 } },
    series: [{ type: 'bar', data: top.map(function (r) { return r.lift; }),
      barWidth: '55%', itemStyle: { color: '#c23531' },
      label: { show: true, position: 'right', formatter: function (p) { return p.value.toFixed(2); } } }]
  });
}

async function toPairs(api) {
  var res = await fetch(api);
  if (!res.ok) throw new Error('接口错误 ' + api);
  var data = await res.json();
  return Object.keys(data).map(function (name) { return { name: name, value: Number(data[name]) }; });
}

document.addEventListener('DOMContentLoaded', function () {
  async function boot() {
    try {
      var freq = await (await fetch('/api/rules/frequent')).json();
      drawFreq(freq); statusEl.textContent = '频繁项集 ' + freq.length + ' 条';
    } catch (e) { console.warn('频繁项集加载失败', e); }
    try {
      var rules = await (await fetch('/api/rules/strong')).json();
      drawScatter(rules); statusEl.textContent += '｜强规则 ' + rules.length + ' 条';
    } catch (e) { console.warn('散点图加载失败', e); }
    try {
      var kw = await toPairs('/api/stats/keyword');
      drawKeyword(kw); statusEl.textContent += '｜词云 ' + kw.length + ' 个关键词';
    } catch (e) { console.warn('词云加载失败', e); }
    try {
      var r2 = await (await fetch('/api/rules/strong')).json();
      drawRules(r2); statusEl.textContent += '｜Top' + Math.min(12, r2.length) + ' 强规则';
    } catch (e) { console.warn('强规则柱图加载失败', e); }
  }
  boot().catch(function (e) { console.error('加载失败', e); statusEl.textContent = '加载失败：' + e.message; });
});
"""


def export_day08_dashboard(out_dir: str = None) -> str:
    """生成 day8 风格 4-panel 大屏（index.html + app.js + 本地 echarts 库）。
    部署到 Spring Boot static 目录后，浏览器访问 http://VM:8080/ 即可。
    """
    out_dir = out_dir or CHART_DIR
    os.makedirs(out_dir, exist_ok=True)
    _ensure_echarts_libs()

    # index.html
    idx_path = os.path.join(out_dir, "index.html")
    with open(idx_path, "w", encoding="utf-8") as f:
        f.write(_INDEX_TPL)
    # app.js
    app_path = os.path.join(out_dir, "app.js")
    with open(app_path, "w", encoding="utf-8") as f:
        f.write(_APP_JS)
    print(f"  day8 大屏: {idx_path}")
    print(f"  day8 大屏: {app_path}")
    return idx_path


def export_echarts_network(rules: pd.DataFrame, top_n: int = TOP_N_RULES,
                            out_path: str = None) -> str:
    """保留旧版独立规则网络图（备用，未部署到大屏）。"""
    out_path = out_path or os.path.join(CHART_DIR, "rules_network.html")
    df = rules.head(top_n).copy()
    nodes_set = set()
    links = []
    for _, r in df.iterrows():
        a = list(r["antecedents"]) if not isinstance(r["antecedents"], str) else [r["antecedents"]]
        c = list(r["consequents"]) if not isinstance(r["consequents"], str) else [r["consequents"]]
        for x in a:
            for y in c:
                nodes_set.add(x); nodes_set.add(y)
                links.append({"source": x, "target": y,
                              "value": round(float(r["lift"]), 3),
                              "conf": round(float(r["confidence"]), 3)})
    nodes = [{"name": n, "symbolSize": 30} for n in nodes_set]
    tpl = """<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8">
<title>关联规则网络</title>
<script src="https://cdn.jsdelivr.net/npm/echarts@5/dist/echarts.min.js"></script>
<style>html,body,#main{height:100%;margin:0}</style></head><body><div id="main"></div>
<script>var c=echarts.init(document.getElementById('main'));c.setOption({title:{text:'关联规则网络',left:'center'},tooltip:{},series:[{type:'graph',layout:'force',roam:true,label:{show:true},force:{repulsion:300,edgeLength:[80,200]},data:__N__,links:__L__,lineStyle:{color:'#999',curveness:0.2},emphasis:{focus:'adjacency'}}]});</script>
</body></html>"""
    html = tpl.replace("__N__", json.dumps(nodes, ensure_ascii=False))
    html = html.replace("__L__", json.dumps(links, ensure_ascii=False))
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)
    return out_path


def export_echarts_heatmap(rules: pd.DataFrame, top_n: int = TOP_N_RULES,
                            out_path: str = None) -> str:
    """保留旧版独立规则热力图（备用）。"""
    out_path = out_path or os.path.join(CHART_DIR, "rules_heatmap.html")
    df = rules.head(top_n).copy()
    data, x_labels, y_labels = [], [], []
    for _, r in df.iterrows():
        a = ",".join(sorted(r["antecedents"])) if not isinstance(r["antecedents"], str) else r["antecedents"]
        c = ",".join(sorted(r["consequents"])) if not isinstance(r["consequents"], str) else r["consequents"]
        if a not in x_labels: x_labels.append(a)
        if c not in y_labels: y_labels.append(c)
        data.append([x_labels.index(a), y_labels.index(c), round(float(r["lift"]), 3)])
    tpl = """<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8">
<title>关联规则热力图</title><script src="https://cdn.jsdelivr.net/npm/echarts@5/dist/echarts.min.js"></script>
<style>html,body,#main{height:100%;margin:0}</style></head><body><div id="main" style="height:80vh"></div>
<script>var c=echarts.init(document.getElementById('main'));c.setOption({tooltip:{position:'top'},grid:{left:'25%',right:'10%',bottom:'15%'},xAxis:{type:'category',data:__X__,axisLabel:{rotate:45}},yAxis:{type:'category',data:__Y__},visualMap:{min:1,max:3,calculable:true,orient:'horizontal',left:'center',bottom:'2%'},series:[{name:'lift',type:'heatmap',data:__D__,label:{show:true},emphasis:{itemStyle:{shadowBlur:10}}]}]});</script>
</body></html>"""
    html = tpl.replace("__X__", json.dumps(x_labels, ensure_ascii=False))
    html = html.replace("__Y__", json.dumps(y_labels, ensure_ascii=False))
    html = html.replace("__D__", json.dumps(data, ensure_ascii=False))
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)
    return out_path
