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

/* =========================================================
   v49 · Helpers UI globales: tooltips y toasts
   ========================================================= */
(function(){
  function removeHelp(){ document.querySelectorAll('.helpPopoverV49').forEach(function(e){e.remove();}); }
  function placeHelp(el, text){
    removeHelp();
    var pop=document.createElement('div');
    pop.className='helpPopoverV49';
    pop.textContent=text;
    document.body.appendChild(pop);
    var r=el.getBoundingClientRect();
    var pr=pop.getBoundingClientRect();
    var left=Math.max(14, Math.min(window.innerWidth-pr.width-14, r.left + r.width/2 - pr.width/2));
    var top=Math.max(14, r.top - pr.height - 12);
    if(top < 20){ top = r.bottom + 12; }
    pop.style.left=left+'px';
    pop.style.top=top+'px';
    setTimeout(function(){pop.classList.add('show');},10);
    setTimeout(removeHelp,4200);
  }
  window.fjordToastV49=function(message,type){
    if(!message) return;
    var stack=document.querySelector('.fjordToastStackV49');
    if(!stack){ stack=document.createElement('div'); stack.className='fjordToastStackV49'; document.body.appendChild(stack); }
    var t=document.createElement('div');
    var kind=type||'info';
    t.className='fjordToastV49 '+kind;
    var icon=kind==='err'?'!':(kind==='warn'?'i':'✓');
    t.innerHTML='<span class="tIcon">'+icon+'</span><span class="tText"></span><button type="button" class="tClose" aria-label="Cerrar aviso">×</button>';
    t.querySelector('.tText').textContent=message;
    t.querySelector('.tClose').addEventListener('click',function(){t.remove();});
    stack.appendChild(t);
    setTimeout(function(){t.classList.add('show');},10);
    setTimeout(function(){t.classList.remove('show'); setTimeout(function(){t.remove();},220);},4200);
  };
  var adminMsgs={
    usuario_creado:['Usuario creado correctamente.','ok'], usuario_existente:['Ya existe un usuario con ese documento.','err'], datos_usuario_invalidos:['Revisá nombre, documento y rol.','err'], rol_invalido:['Rol inválido.','err'], clave_reseteada:['Clave reseteada a demo1234.','ok'], usuario_actualizado:['Usuario actualizado.','ok'], salida_creada:['Navegación creada correctamente.','ok'], salida_actualizada:['Salida actualizada.','ok'], estado_actualizado:['Estado actualizado.','ok'], estado_invalido:['Estado inválido.','err'], json_restaurado:['Restauración JSON desactivada en producción.','err'], json_importado:['Importación JSON desactivada en producción.','err'], demo_reset:['Reset demo desactivado en producción.','err']
  };
  document.addEventListener('click',function(e){
    var h=e.target.closest('[data-tip]');
    if(h){ e.preventDefault(); e.stopPropagation(); placeHelp(h, h.getAttribute('data-tip')); return; }
    removeHelp();
  });
  document.addEventListener('DOMContentLoaded',function(){
    var body=document.body;
    var code=body ? body.getAttribute('data-admin-msg') : '';
    if(code && adminMsgs[code]){ window.fjordToastV49(adminMsgs[code][0], adminMsgs[code][1]); }
    var inline=document.querySelector('[data-toast-message]');
    if(inline){ window.fjordToastV49(inline.getAttribute('data-toast-message'), inline.getAttribute('data-toast-type')||'info'); }
  });
})();
