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
      + '<a href="/dashboard.html"' + (activePage==='dashboard'?' class="active"':'') + '>数据大屏</a>';
  } else {
    menuHtml =
      '<a href="/index.html"' + (activePage==='home'?' class="active"':'') + '>首页</a>'
      + '<a href="/search.html"' + (activePage==='search'?' class="active"':'') + '>找工作</a>'
      + '<a href="/user/index.html"' + (activePage==='user-home'?' class="active"':'') + '>个人主页</a>'
      + '<a href="/user/resume.html"' + (activePage==='user-resume'?' class="active"':'') + '>我的简历</a>'
      + '<a href="/user/chat.html"' + (activePage==='user-chat'?' class="active"':'') + '>我的消息</a>'
      + '<a href="/predict.html"' + (activePage==='predict'?' class="active"':'') + '>薪资预测</a>'
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
