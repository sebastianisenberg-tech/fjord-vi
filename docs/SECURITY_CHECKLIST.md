# Checklist de seguridad Fjord VI

## Acceso
- Passwords hasheados, nunca en texto plano.
- Cambio obligatorio cuando la clave temporal sea `demo1234`.
- Sesiones con vencimiento.
- Logout explícito.
- Bloqueo gradual por intentos de login.

## Roles
- Socio solo accede a su vista y acciones permitidas.
- Capitán solo opera embarque, presencia, cierre y reapertura permitida.
- Administración accede a padrón, salidas, sistema y auditoría.
- Las rutas admin deben rechazar usuarios no admin.

## Formularios críticos
- Reset de clave con confirmación.
- Reset operativo total con frase exacta y checkbox.
- Acciones destructivas siempre auditadas.
- Inputs validados y normalizados.

## Secretos
- `DATABASE_URL`, `SECRET_KEY` y SMTP solo por variables de entorno.
- No subir `.env` real.
- No hardcodear claves en el repositorio.

## Errores
- No mostrar traceback ni JSON técnico al usuario final.
- Las rutas rotas deben ir a pantalla humana o redirección segura.

## Backups
- Backup SQL disponible antes de acciones irreversibles.
- Snapshot previo a reset operativo.
- Restauración documentada antes de producción real.
