'use strict';
// ===== 共享工具：导航栏注入 + fetch 封装 + 登录态 =====

// 获取当前用户名（从 localStorage）
function currentUser() {
  return localStorage.getItem('recruit_username') || null;
}
function getToken() {
  return localStorage.getItem('recruit_token') || null;
}
function logout() {
  localStorage.removeItem('recruit_token');
  localStorage.removeItem('recruit_username');
  localStorage.removeItem('recruit_role');
  localStorage.removeItem('recruit_company');
  location.href = '/index.html';
}

var DEFAULT_CITIES = [
  '北京','上海','广州','深圳','杭州','成都','南京','武汉','西安','长沙','苏州','重庆','天津','青岛','厦门',
  '宁波','郑州','合肥','福州','济南','大连','沈阳','长春','哈尔滨','石家庄','太原','南昌','南宁','昆明',
  '贵阳','兰州','西宁','银川','乌鲁木齐','呼和浩特','海口','三亚','珠海','东莞','佛山','无锡','常州',
  '南通','徐州','温州','绍兴','嘉兴','泉州','烟台','潍坊','洛阳'
];

// 城市下拉统一从岗位数据动态加载；接口异常时使用完整城市池兜底。
async function loadCityOptions(selectId, placeholder, selectedValue) {
  var select = document.getElementById(selectId);
  if (!select) return [];
  var cities = [];
  try {
    cities = await api('/api/job/cities');
  } catch (e) {}
  if (!Array.isArray(cities) || cities.length === 0) cities = DEFAULT_CITIES;
  var current = selectedValue !== undefined ? selectedValue : select.value;
  select.innerHTML = '<option value="">' + (placeholder || '选择城市') + '</option>';
  cities.forEach(function(city) {
    var option = document.createElement('option');
    option.value = city;
    option.textContent = city;
    select.appendChild(option);
  });
  if (current && cities.indexOf(current) >= 0) select.value = current;
  return cities;
}

// 带鉴权的 fetch
async function api(url, opts) {
  opts = opts || {};
  var token = getToken();
  var headers = opts.headers ? Object.assign({}, opts.headers) : {};
  if (token) headers['Authorization'] = 'Bearer ' + token;
  if (opts.body) headers['Content-Type'] = 'application/json';
  opts.headers = headers;
  var resp = await fetch(url, opts);
  return resp.json();
}

// 注入导航栏 (按角色区分)
function injectNavbar(activePage) {
  var user = currentUser();
  var role = localStorage.getItem('recruit_role') || 'user';
  var menuHtml = '';
  if (role === 'company') {
    menuHtml =
      '<a href="/company/index.html"' + (activePage==='company-home'?' class="active"':'') + '>企业主页</a>'
      + '<a href="/company/jobs.html"' + (activePage==='company-jobs'?' class="active"':'') + '>岗位管理</a>'
      + '<a href="/company/talent.html"' + (activePage==='company-talent'?' class="active"':'') + '>人才浏览</a>'
      + '<a href="/company/chat.html"' + (activePage==='company-chat'?' class="active"':'') + '>消息中心</a>'
      + '<a href="/change-password.html"' + (activePage==='change-password'?' class="active"':'') + '>修改密码</a>'
      + '<a href="/dashboard.html"' + (activePage==='dashboard'?' class="active"':'') + '>数据大屏</a>';
  } else {
    menuHtml =
      '<a href="/index.html"' + (activePage==='home'?' class="active"':'') + '>首页</a>'
      + '<a href="/search.html"' + (activePage==='search'?' class="active"':'') + '>找工作</a>'
      + '<a href="/user/index.html"' + (activePage==='user-home'?' class="active"':'') + '>个人主页</a>'
      + '<a href="/user/resume.html"' + (activePage==='user-resume'?' class="active"':'') + '>我的简历</a>'
      + '<a href="/user/chat.html"' + (activePage==='user-chat'?' class="active"':'') + '>我的消息</a>'
      + '<a href="/predict.html"' + (activePage==='predict'?' class="active"':'') + '>薪资预测</a>'
      + '<a href="/change-password.html"' + (activePage==='change-password'?' class="active"':'') + '>修改密码</a>'
      + '<a href="/dashboard.html"' + (activePage==='dashboard'?' class="active"':'') + '>数据大屏</a>';
  }
  var userArea = user
    ? '<span class="user-name">' + user + (role==='company'?' [企业]':'') + '</span>'
      + '<button class="btn-logout" onclick="logout()">退出</button>'
    : '<a href="/login.html" class="btn-login">登录</a>'
      + '<a href="/register.html" class="btn-login" style="margin-left:8px">注册</a>';
  var html =
    '<nav class="navbar">'
    + '<div class="logo">智<span>聘</span> · 招聘分析平台</div>'
    + '<div class="menu">' + menuHtml + '</div>'
    + '<div class="user-area">' + userArea + '</div>'
    + '</nav>';
  var c = document.getElementById('navbar-container');
  if (c) c.innerHTML = html;
}

// 岗位卡片 HTML
function jobCardHTML(job) {
  var tags = (job.tags || '').split(';').filter(function(t){return t;}).map(function(t){
    return '<span class="tag">' + t + '</span>';
  }).join('');
  return '<div class="job-card" onclick="location.href=\'/detail.html?id=' + job.rowKey + '\'">'
    + '<div class="job-main">'
    + '<div class="job-title">' + (job.title||'') + '</div>'
    + '<div class="job-company">' + (job.company||'') + ' · ' + (job.city||'') + ' · ' + (job.edu||'') + ' · ' + (job.exp||'') + '</div>'
    + '<div class="job-tags">' + tags + '</div>'
    + '</div>'
    + '<div class="job-salary">' + (job.salary_low||'') + '-' + (job.salary_high||'') + 'K</div>'
    + '</div>';
}

// 分页 HTML
function paginationHTML(page, totalPages) {
  var h = '<div class="pagination">';
  h += '<button onclick="doSearch(' + (page-1) + ')" ' + (page<=1?'disabled':'') + '>上一页</button>';
  var start = Math.max(1, page-2);
  var end = Math.min(totalPages, page+2);
  for (var i = start; i <= end; i++) {
    h += '<button class="' + (i===page?'active':'') + '" onclick="doSearch(' + i + ')">' + i + '</button>';
  }
  h += '<button onclick="doSearch(' + (page+1) + ')" ' + (page>=totalPages?'disabled':'') + '>下一页</button>';
  h += '</div>';
  return h;
}
