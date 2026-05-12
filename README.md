# Fjord VI 1.2.2

Paquete limpio de producción basado en la versión funcional 1.18.18.

Objetivo:
- mantener la lógica operativa vigente
- reducir ruido en el deploy
- eliminar archivos históricos y duplicados que no participan de la ejecución

Se conservaron:
- código necesario para correr en Render
- templates y static en uso
- migraciones
- metadata y documentación esencial

Se eliminaron del deploy:
- auditorías históricas sueltas
- tests
- scripts de release no necesarios en runtime
- diagnósticos históricos
- duplicados y archivos espejo no usados por el entrypoint real

Versión actual: **Fjord VI · v1.2.2**


Incluye restauración mínima de blindaje formal: tests scaffold, tests críticos de negocio y script externo de release.
