Fjord VI v3.7.3.1 · Comunicaciones Control Final

Objetivo:
Consolidar Comunicaciones con un estado maestro inequívoco, semáforos de seguridad, alerta de cola, preview de plantillas y controles claros de producción.

Agregado:
- Estado general SMTP.
- Detección de configuraciones inconsistentes.
- Alerta de cola trabada o pendiente.
- Preview renderizado JSON de cada plantilla.
- Nota de auditoría SMTP.
- Freeze de producción con instrucciones.
- Versión visible SMTP · v3.7.3.1.1.1.

Secuencia recomendada:
1. Cargar configuración SMTP.
2. Guardar.
3. Validar SMTP.
4. Enviar prueba.
5. Probar plantillas.
6. Ejecutar prueba integral.
7. Encender eventos de a uno.
8. Recién después evaluar producción real.
