'use strict';
(function () {
  const root = document.querySelector('[data-announcements]');
  if (!root) return;
  const mode = root.dataset.announcements, admin = mode === 'admin', home = mode === 'home';
  const el = id => document.getElementById('announcement-' + id);
  let page = 1, total = 0, loading = false, busy = false, editing = null;
  const size = home ? 3 : 10;
  if (!home) injectNavbar(admin ? 'admin-announcements' : 'announcements');
  if (admin && (!getToken() || localStorage.getItem('recruit_role') !== 'admin')) return;
  function status(id, message, error = false) {
    el(id).textContent = message;
    el(id).classList.toggle('error', error);
  }
  async function request(path, body) {
    const result = await api(path, body === undefined ? undefined : {method:'POST', body:JSON.stringify(body)});
    if (result.code !== 0) throw new Error(result.msg || '请求失败，请稍后重试');
    return result;
  }
  function date(value) { return new Date(Number(value)).toLocaleString('zh-CN'); }
  function metadata(item) { return '管理员 · 发布于 ' + date(item.publishedAt); }
  function controls() {
    root.querySelectorAll('button').forEach(button => { button.disabled = busy || loading; });
    if (el('prev')) el('prev').disabled = busy || loading || page <= 1;
    if (el('next')) el('next').disabled = busy || loading || page * size >= total;
    if (admin) { el('input-title').disabled = busy; el('input-body').disabled = busy; }
  }
  function node(tag, text, className) {
    const element = document.createElement(tag); element.textContent = text;
    if (className) element.className = className;
    return element;
  }
  function resetEditor() {
    editing = null; el('form').reset(); el('editor-title').textContent = '发布公告';
    el('save').textContent = '发布公告'; el('cancel').hidden = true;
  }
  async function edit(item) {
    busy = true; controls(); status('form-status', '正在加载公告…');
    try {
      const result = await request('/api/announcements/' + encodeURIComponent(item.id));
      editing = item.id; el('input-title').value = result.item.title; el('input-body').value = result.item.body;
      el('editor-title').textContent = '编辑公告'; el('save').textContent = '保存修改'; el('cancel').hidden = false;
      status('form-status', '正在编辑：' + result.item.title);
      el('form').scrollIntoView({behavior:'smooth', block:'start'});
    } catch (error) { status('form-status', error.message, true); }
    finally { busy = false; controls(); if (editing === item.id) el('input-title').focus({preventScroll:true}); }
  }
  async function remove(item) {
    if (!confirm('确定删除公告“' + item.title + '”？删除后无法恢复。')) return;
    busy = true; controls(); status('form-status', '正在删除…');
    try {
      await request('/api/admin/announcements/' + encodeURIComponent(item.id) + '/delete', {});
      if (editing === item.id) resetEditor();
      status('form-status', '公告已删除'); await loadList();
    } catch (error) { status('form-status', error.message, true); }
    finally { busy = false; controls(); }
  }
  function renderItem(item) {
    const row = node('article', '', 'announcement-row');
    const title = node('h3', ''), link = node('a', item.title);
    link.href = '/announcement.html?id=' + encodeURIComponent(item.id); title.appendChild(link);
    row.append(title, node('p', metadata(item), 'announcement-meta'));
    if (admin) {
      const actions = node('div', '', 'announcement-actions');
      const editButton = node('button', '编辑', 'secondary'), deleteButton = node('button', '删除', 'danger');
      editButton.setAttribute('aria-label', '编辑：' + item.title); deleteButton.setAttribute('aria-label', '删除：' + item.title);
      editButton.onclick = () => edit(item); deleteButton.onclick = () => remove(item);
      actions.append(editButton, deleteButton); row.appendChild(actions);
    }
    return row;
  }
  async function loadList() {
    loading = true; controls(); el('retry').hidden = true; status('status', '正在加载公告…');
    el('list').replaceChildren(); if (el('page-label')) el('page-label').textContent = '';
    try {
      let result = await request('/api/announcements?page=' + page + '&size=' + size);
      total = result.total;
      const lastPage = Math.max(1, Math.ceil(total / size));
      if (page > lastPage) { page = lastPage; result = await request('/api/announcements?page=' + page + '&size=' + size); total = result.total; }
      result.items.forEach(item => el('list').appendChild(renderItem(item)));
      status('status', total ? '' : '暂无公告');
      if (el('page-label')) el('page-label').textContent = page + ' / ' + Math.max(1, Math.ceil(total / size)) + ' 页 · 共 ' + total + ' 条';
    } catch (error) { status('status', error.message || '公告加载失败', true); el('retry').hidden = false; }
    finally { loading = false; controls(); }
  }
  async function loadDetail() {
    el('retry').hidden = true; el('detail').hidden = true; status('status', '正在加载公告…');
    const id = new URLSearchParams(location.search).get('id');
    if (!id) { status('status', '公告不存在或已删除', true); return; }
    try {
      const {item} = await request('/api/announcements/' + encodeURIComponent(id));
      el('title').textContent = item.title; el('body').textContent = item.body;
      el('meta').textContent = metadata(item) + (item.updatedAt !== item.publishedAt ? ' · 更新于 ' + date(item.updatedAt) : '');
      document.title = item.title + ' · 智聘公告'; el('detail').hidden = false; status('status', '');
    } catch (error) { status('status', error.message, true); el('retry').hidden = false; }
  }
  if (mode === 'detail') { el('retry').onclick = loadDetail; loadDetail(); return; }
  el('retry').onclick = loadList;
  if (!home) {
    el('prev').onclick = () => { if (!busy && !loading && page > 1) { page--; loadList(); } };
    el('next').onclick = () => { if (!busy && !loading && page * size < total) { page++; loadList(); } };
  }
  if (admin) {
    el('cancel').onclick = () => { resetEditor(); status('form-status', ''); };
    el('form').onsubmit = async event => {
      event.preventDefault(); if (busy || loading) return;
      const title = el('input-title').value.trim(), body = el('input-body').value.trim();
      if (!title || !body || Array.from(title).length > 100 || Array.from(body).length > 10000) {
        status('form-status', '标题须为 1–100 字，正文须为 1–10,000 字', true); return;
      }
      busy = true; controls(); status('form-status', '正在保存…');
      const wasEditing = Boolean(editing);
      try {
        await request('/api/admin/announcements' + (editing ? '/' + encodeURIComponent(editing) + '/update' : ''), {title, body});
        resetEditor(); status('form-status', wasEditing ? '修改已保存' : '公告已发布');
        if (!wasEditing) page = 1;
        await loadList();
      } catch (error) { status('form-status', error.message, true); }
      finally { busy = false; controls(); }
    };
  }
  loadList();
})();
