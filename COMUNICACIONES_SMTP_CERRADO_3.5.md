Fjord VI v3.7.7 · Comunicaciones SMTP cerrado

Objetivo:
Cerrar el módulo de Comunicaciones para iniciar pruebas reales de correo sin seguir iterando la pantalla.

Incluye:
- Lista explícita de requisitos faltantes.
- Semáforos ampliados.
- Último email enviado.
- Estado de scheduler/procesamiento.
- Modo simulación para generar cola sin envío SMTP real.
- Prueba individual por plantilla.
- Registro con estado vacío explícito.
- Versión visible SMTP · v3.7.7.

Secuencia:
1. Cargar configuración SMTP.
2. Cargar receptor de pruebas.
3. Guardar.
4. Validar SMTP.
5. Enviar prueba.
6. Ejecutar prueba integral SMTP.
7. Encender eventos uno por uno.
8. Probar acciones reales del sistema.
