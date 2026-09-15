'use strict';
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
  // 修复错位：data 用纯数字数组 [conf, lift, support, 索引]
  // rule 存外部 map 按 dataIndex 查，避免字符串进 visualMap 导致颜色/位置错乱
  var ruleMap = {};
  var data = rules.map(function (r, i) { ruleMap[i] = r.rule; return [r.confidence, r.lift, r.support, i]; });
  scatterEl.setOption({
    title: { text: '置信度 vs 提升度', left: 'center' },
    tooltip: { trigger: 'item', formatter: function (p) {
      var d = p.data;
      return ruleMap[d[3]] + '<br/>conf=' + d[0].toFixed(3) + '  lift=' + d[1].toFixed(3) + '  support=' + d[2].toFixed(3); } },
    grid: { left: '10%', right: '18%', top: 40, bottom: 50 },
    xAxis: { type: 'value', name: 'confidence', min: 0, max: 1.0, nameLocation: 'middle', nameGap: 28,
             axisLabel: { formatter: function (v) { return v.toFixed(1); } } },
    yAxis: { type: 'value', name: 'lift' },
    // dimension:1 按 lift 映射颜色；放右上竖向，避免与 X 轴标签重叠
    visualMap: { min: 1, max: 15, dimension: 1, calculable: true, orient: 'vertical',
                 right: 10, top: 50,
                 inRange: { color: ['#f5d4d4', '#c23531'] },
                 text: ['lift高', 'lift低'],
                 itemHeight: 120 },
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
