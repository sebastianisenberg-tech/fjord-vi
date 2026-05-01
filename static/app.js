(function(){
  function ready(fn){ if(document.readyState !== 'loading') fn(); else document.addEventListener('DOMContentLoaded', fn); }

  function ensureToastHost(){
    var host = document.getElementById('appToastHost');
    if(!host){
      host = document.createElement('div');
      host.id = 'appToastHost';
      host.className = 'appToastHost';
      document.body.appendChild(host);
    }
    return host;
  }

  function cleanMessage(text){
    if(!text) return 'No se pudo completar la operación.';
    try {
      var parsed = JSON.parse(text);
      if(parsed && parsed.detail) return String(parsed.detail);
    } catch(e) {}
    var div = document.createElement('div');
    div.innerHTML = text;
    var body = (div.textContent || div.innerText || '').replace(/\s+/g,' ').trim();
    if(!body) return 'No se pudo completar la operación.';
    if(body.length > 220) body = body.slice(0, 220) + '...';
    return body;
  }

  function showAppToast(message, type){
    var host = ensureToastHost();
    var item = document.createElement('div');
    item.className = 'appToastNotice ' + (type || 'info');
    item.setAttribute('role','status');
    item.setAttribute('aria-live','polite');
    var title = type === 'error' ? 'No se pudo realizar la acción' : (type === 'success' ? 'Operación realizada' : 'Aviso');
    item.innerHTML = '<div class="toastIcon">' + (type === 'error' ? '!' : '✓') + '</div><div><b>'+ title +'</b><span></span></div><button type="button" aria-label="Cerrar aviso">×</button>';
    item.querySelector('span').textContent = message;
    item.querySelector('button').addEventListener('click', function(){ item.classList.add('leaving'); setTimeout(function(){ item.remove(); }, 180); });
    host.appendChild(item);
    requestAnimationFrame(function(){ item.classList.add('visible'); });
    setTimeout(function(){ if(item.isConnected){ item.classList.add('leaving'); setTimeout(function(){ item.remove(); }, 180); } }, type === 'error' ? 6200 : 3600);
  }

  window.showAppToast = showAppToast;

  ready(function(){
    var params = new URLSearchParams(window.location.search);
    var msg = params.get('msg');
    var error = params.get('error');
    if(error){ showAppToast('Revisá usuario y contraseña, o volvé a intentar.', 'error'); }
    if(msg === 'socio_responsable_no_embarca'){
      showAppToast('No se puede marcar presente a un invitado si el socio responsable no está presente y activo.', 'error');
    }

    document.querySelectorAll('form[method="post"], form[method="POST"]').forEach(function(form){
      if(form.dataset.noAjax === '1' || form.enctype === 'multipart/form-data') return;
      form.addEventListener('submit', function(ev){
        if(ev.defaultPrevented) return;
        ev.preventDefault();
        var btns = Array.prototype.slice.call(form.querySelectorAll('button'));
        btns.forEach(function(btn){ btn.disabled = true; btn.classList.add('disabledBtn'); });
        var action = form.getAttribute('action') || window.location.pathname;
        var method = (form.getAttribute('method') || 'post').toUpperCase();
        fetch(action, { method: method, body: new FormData(form), credentials: 'same-origin', redirect: 'follow' })
          .then(function(resp){
            if(resp.redirected){ window.location.href = resp.url; return null; }
            if(resp.ok){ window.location.reload(); return null; }
            return resp.text().then(function(text){ throw new Error(cleanMessage(text)); });
          })
          .catch(function(err){
            showAppToast(err && err.message ? err.message : 'No se pudo completar la operación.', 'error');
            btns.forEach(function(btn){ btn.disabled = false; btn.classList.remove('disabledBtn'); });
          });
      });
    });
  });
})();
