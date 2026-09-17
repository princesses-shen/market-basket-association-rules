'use strict';
// Each form retains its own cooldown; changing identity never reuses the entered code.
function emailCodeForm(options) {
  var button = document.getElementById(options.button);
  var code = document.getElementById(options.code);
  var message = document.getElementById(options.message);
  var pending = false;
  function key(identity) { return 'email-code:' + options.path + ':' + JSON.stringify(identity); }
  function render() {
    var remaining = Math.max(0, Math.ceil((Number(sessionStorage.getItem(key(options.identity()))) - Date.now()) / 1000));
    button.disabled = pending || remaining > 0;
    button.textContent = pending ? '正在发送…' : remaining > 0 ? remaining + ' 秒后重发' : '发送验证码';
  }
  function changed() { code.value = ''; message.textContent = ''; render(); }
  options.fields.forEach(function (id) {
    var field = document.getElementById(id);
    field.addEventListener('input', changed);
    field.addEventListener('change', changed);
  });
  button.addEventListener('click', async function () {
    if (button.disabled || pending) return;
    var identity = options.identity();
    if (!identity.username || !identity.email || !options.valid()) {
      message.textContent = '请填写账号和有效邮箱'; return;
    }
    pending = true; code.value = ''; render(); message.textContent = '正在发送…';
    try {
      var result = await api(options.path, {method:'POST', body:JSON.stringify(identity)});
      if (result.code === 0 || result.code === 429) sessionStorage.setItem(key(identity), String(Date.now() + 60000));
      if (key(identity) === key(options.identity())) message.textContent = result.msg || '发送失败，请稍后重试';
    } catch (error) {
      if (key(identity) === key(options.identity())) message.textContent = error.message || '网络连接失败，请重试';
    } finally { pending = false; render(); }
  });
  var timer = setInterval(render, 1000);
  window.addEventListener('pagehide', function () { clearInterval(timer); });
  render();
  return {clear:changed};
}
