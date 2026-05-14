# Migraciones

Carpeta preparada para migraciones SQL versionadas.

En producción profesional, cada cambio de estructura de base debería tener un archivo:

```text
001_initial_schema.sql
002_add_activity_log.sql
003_add_notifications.sql
```

Por ahora el sistema conserva reparación segura interna desde la consola Sistema.
