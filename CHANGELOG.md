# v38.9.0

- Refinamiento premium específico para socios.
- Mejor jerarquía visual de salidas, reserva titular, invitados y reglas.
- Estados operativos más visibles y separados de etiquetas secundarias.
- Formularios e inputs más claros para Android, iPhone y escritorio.
- Mejor feedback táctil y navegación inferior más legible.
- Sin cambios en backend, rutas ni lógica de reservas.

# v38.8.0

- Segunda verificación interna del paquete.
- Corrige metadatos de versión inconsistentes.
- Evita pantallas 400 feas en acciones críticas del capitán: cierre anticipado, ventana finalizada, reserva en espera y salida inexistente vuelven con aviso superior dentro de la app.
- Caso invitado sin socio responsable presente: muestra aviso explícito y no cambia silenciosamente el estado a No embarca.
- Mantiene backend estructural, rutas y lógica principal sin rediseño.

# v38.3.0

- Afinado de densidad visual premium.
- Barras horizontales más finas.
- Botones más compactos con tacto soft/iOS.
- Cards, KPIs, formularios y navegación inferior con menor peso visual.
- Sin cambios de backend ni de lógica operativa.

# v38.3.0

- Ajuste premium de interfaz: botones más delicados, menos pesados y con estados semánticos.
- Capitán: Presente verde, No embarca rojo, Reactivar ámbar.
- Administración: etiquetas más claras: Confirmados y Check-in a bordo.
- Hora operativa local fija para Argentina/Uruguay mediante APP_TZ, por defecto America/Argentina/Buenos_Aires.
- No se modificó la arquitectura ni la lógica principal de reservas/lista de espera.

# v38.1.0

- Limpieza de ZIP: elimina copias duplicadas de CSS e imágenes en raíz.
- Mantiene solo `/static/style.css` y recursos dentro de `/static`.
- Confirma HTML plano en raíz, sin carpeta `/templates`.
- Mantiene fix Jinja `g["items"]` en admin, socio y capitán.
- Mantiene `SafeTemplates` para evitar errores 500 opacos.

# v38.0.0

- Corrige `admin.html` con `g["items"]`.
- Agrega recursos estáticos en `/static`.
- Mantiene proyecto plano.

## v38.6.0 - Header fijo de app
- Recupera la barra superior fija en socio, capitán y administración.
- El contenido vuelve a deslizar por debajo del header, manteniendo identidad y salida siempre visibles.
- No modifica backend, rutas ni lógica de reservas.
