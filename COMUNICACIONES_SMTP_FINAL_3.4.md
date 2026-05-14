Fjord VI v3.7.8 · Comunicaciones SMTP final

Objetivo:
Dejar una pantalla única de comunicaciones lista para testear correo sin seguir generando versiones intermedias.

Incluye:
- Versión visible del módulo.
- Semáforos de SMTP, receptor de pruebas, modo prueba, redirect, validación, fallidos, pendientes y eventos ON.
- Botón Validar SMTP.
- Botón Prueba integral SMTP.
- Bloque de seguridad: si TEST MODE está activo y el redirect está activo, ningún socio real recibe correos.
- Configuración completa de host, puerto, usuario, App Password, remitente, administración y receptor de pruebas.
- Cola y plantillas en la misma pantalla.

Secuencia recomendada:
1. Cargar SMTP.
2. Cargar receptor de pruebas.
3. Dejar Modo prueba, Redirect y Bloqueo activos.
4. Guardar configuración.
5. Validar SMTP.
6. Enviar prueba manual.
7. Ejecutar Prueba integral SMTP.
8. Encender eventos uno por uno.
9. Procesar cola y revisar registro.
