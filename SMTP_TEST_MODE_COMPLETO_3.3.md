Fjord VI v3.5 · SMTP completa

Configuración recomendada para testeo con Gmail:
- SMTP host: smtp.gmail.com
- Puerto: 587
- Usuario: cuenta Gmail completa
- Password: App Password de Google, no la contraseña normal
- Remitente email: la misma cuenta Gmail
- Nombre remitente: YCA · Fjord VI TEST
- Email administración: email de administración o tester
- Email receptor de pruebas: email donde deben llegar todos los correos

Seguridad:
- Modo prueba SMTP activo
- Redirigir todos los correos al receptor de pruebas activo
- Bloquear destinatarios reales durante pruebas activo

Secuencia de prueba:
1. Guardar configuración SMTP.
2. Enviar prueba manual.
3. Usar Prueba integral SMTP.
4. Encender eventos uno por uno.
5. Simular reserva, invitado, lista de espera, cancelación, recordatorio, no-show y cierre.
6. Verificar que todos los correos lleguen solo al receptor de pruebas.
