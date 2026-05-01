# v38.2.0

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
