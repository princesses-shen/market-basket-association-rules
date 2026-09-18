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
  location.href = '/index.html';
}

// All existing fetch callers share the same credential and expiry handling.
function clearLogin() {
  ['recruit_token', 'recruit_username', 'recruit_role', 'recruit_company'].forEach(k => localStorage.removeItem(k));
}
function saveLogin(result) {
  var destinations = {user:'/user/index.html', company:'/company/index.html', admin:'/admin/index.html'};
  if (!result.token || !destinations[result.role]) throw new Error('登录响应无效，请重试');
  clearLogin();
  localStorage.setItem('recruit_token', result.token);
  localStorage.setItem('recruit_username', result.username);
  localStorage.setItem('recruit_role', result.role);
  if (result.role === 'company') localStorage.setItem('recruit_company', result.company_name || result.username);
  location.href = destinations[result.role];
}
(function () {
  var originalFetch = window.fetch.bind(window);
  var loginExpired = false;
  window.fetch = async function (input, options) {
    var url = new URL(input instanceof Request ? input.url : String(input), location.href);
    var sameOrigin = url.origin === location.origin;
    var isAccountForm = /^\/api\/(user|company|admin)\/(login|register)$/.test(url.pathname)
      || /^\/api\/auth\/(password-reset|register|email-login)\/(code|confirm)$/.test(url.pathname);
    var protectedCall = sameOrigin && !isAccountForm
      && (url.pathname.startsWith('/api/') || url.pathname.startsWith('/uploads/'));
    var opts = Object.assign({}, options || {});
    if (protectedCall) {
      var headers = new Headers(opts.headers || (input instanceof Request ? input.headers : undefined));
      if (getToken()) headers.set('Authorization', 'Bearer ' + getToken());
      opts.headers = headers;
    }
    var response = await originalFetch(input, opts);
    if (protectedCall && !response.ok) {
      var detail = await response.clone().json().catch(() => ({}));
      var message = detail.msg || '请求失败，请稍后重试';
      if (response.status === 401 && !loginExpired) {
        loginExpired = true;
        clearLogin();
        sessionStorage.setItem('recruit_login_message', message);
        location.href = '/login.html';
      }
      throw new Error(message);
    }
    return response;
  };
  var section = location.pathname.split('/')[1];
  if (['user', 'company', 'admin'].includes(section)
      && (!getToken() || localStorage.getItem('recruit_role') !== section)) {
    location.replace('/login.html');
  }
  // Attachment links must carry the same bearer token; never put tokens in URLs.
  document.addEventListener('click', async function (event) {
    var link = event.target.closest('a');
    if (!link) return;
    var url = new URL(link.href, location.href);
    if (url.origin !== location.origin) return;
    // 附件类链接包含两种形态：/uploads/{file}（预览或下载）与 /api/files/{file}/download（企业端另存）。
    var isAttachment = url.pathname.startsWith('/uploads/')
      || /^\/api\/files\/.+\/download$/.test(url.pathname);
    if (!isAttachment) return;
    event.preventDefault();
    try {
      var response = await fetch(url.href);
      var blobUrl = URL.createObjectURL(await response.blob());
      // 声明了新窗口且未声明 download 的链接按“在线预览”处理，其余按“另存到本地”处理。
      if (link.target === '_blank' && !link.hasAttribute('download')) {
        window.open(blobUrl, '_blank');
        setTimeout(() => URL.revokeObjectURL(blobUrl), 60000);
        return;
      }
      var download = document.createElement('a');
      download.href = blobUrl;
      var disposition = response.headers.get('Content-Disposition') || '';
      var encodedName = disposition.match(/filename\*=UTF-8''([^;]+)/i);
      download.download = encodedName ? decodeURIComponent(encodedName[1]) : (link.download || '简历附件');
      download.click();
      setTimeout(() => URL.revokeObjectURL(blobUrl), 1000);
    } catch (error) { alert(error.message); }
  });
})();

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
  opts = Object.assign({}, opts || {});
  if (opts.body && !(opts.body instanceof FormData)) {
    opts.headers = Object.assign({'Content-Type':'application/json'}, opts.headers || {});
  }
  var resp = await fetch(url, opts);
  return resp.json();
}
function escapeHtml(value) {
  return String(value == null ? '' : value).replace(/[&<>"']/g, c => ({'&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#39;'}[c]));
}

// 注入导航栏
function injectNavbar(activePage) {
  var user = currentUser();
  var role = localStorage.getItem('recruit_role') || 'user';
  // 求职咨询（origin/main 新增板块）对所有角色可见。
  var forumLink = '<a href="/forum.html"' + (activePage==='forum'?' class="active"':'') + '>求职咨询</a>';
  var menuHtml = '';
  if (role === 'admin') {
    menuHtml =
      '<a href="/index.html"' + (activePage==='home'?' class="active"':'') + '>首页</a>'
      + '<a href="/admin/index.html"' + (activePage==='admin'?' class="active"':'') + '>账号安全管理</a>';
  } else if (role === 'company') {
    menuHtml =
      '<a href="/company/index.html"' + (activePage==='company-home'?' class="active"':'') + '>企业主页</a>'
      + '<a href="/company/jobs.html"' + (activePage==='company-jobs'?' class="active"':'') + '>岗位管理</a>'
      + '<a href="/company/talent.html"' + (activePage==='company-talent'?' class="active"':'') + '>人才浏览</a>'
      + '<a href="/company/chat.html"' + (activePage==='company-chat'?' class="active"':'') + '>消息中心</a>'
      + forumLink
      + '<a href="/change-password.html"' + (activePage==='change-password'?' class="active"':'') + '>修改密码</a>'
      + '<a href="/dashboard.html"' + (activePage==='dashboard'?' class="active"':'') + '>数据大屏</a>';
  } else {
    menuHtml =
      '<a href="/index.html"' + (activePage==='home'?' class="active"':'') + '>首页</a>'
      + '<a href="/search.html"' + (activePage==='search'?' class="active"':'') + '>找工作</a>'
      + forumLink
      + '<a href="/user/index.html"' + (activePage==='user-home'?' class="active"':'') + '>个人主页</a>'
      + '<a href="/user/resume.html"' + (activePage==='user-resume'?' class="active"':'') + '>我的简历</a>'
      + '<a href="/user/chat.html"' + (activePage==='user-chat'?' class="active"':'') + '>我的消息</a>'
      + '<a href="/predict.html"' + (activePage==='predict'?' class="active"':'') + '>薪资预测</a>'
      + '<a href="/change-password.html"' + (activePage==='change-password'?' class="active"':'') + '>修改密码</a>'
      + '<a href="/dashboard.html"' + (activePage==='dashboard'?' class="active"':'') + '>数据大屏</a>';
  }
  var userArea = user
    ? '<span class="user-name">' + escapeHtml(user) + (role==='company'?' [企业]':role==='admin'?' [管理员]':'') + '</span>'
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

// 别名兼容
var loadNav = injectNavbar;
var getCurrentUser = function() {
  var u = currentUser();
  var t = getToken();
  return u ? { username: u, token: t } : null;
};
