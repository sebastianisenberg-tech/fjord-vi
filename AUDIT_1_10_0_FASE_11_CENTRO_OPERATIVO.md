# Fjord VI 1.10.0 - Fase 11 Centro Operativo Inteligente

## Objetivo
Convertir el panel administrativo en una consola de operación humana: mostrar qué está pasando ahora, qué requiere atención, cómo está la salud del padrón y permitir búsqueda transversal sin recorrer módulos.

## Cambios principales
- Versión unificada a 1.10.0.
- Nuevo resumen `phase11_center_summary`.
- Próxima salida viva con plazas, invitados, presentes, pendientes, capitán y ventana de freeze.
- Alertas humanas accionables para operación real.
- Timeline operativo combinando actividad y auditoría.
- Salud de datos del padrón: email, teléfono/WhatsApp, Nº de socio, duplicados.
- Buscador universal sobre usuarios, salidas, reservas y fichas.
- Endpoints `/admin/phase11.json`, `/admin/phase11.txt`, `/admin/search.json`.
- Bloque Fase 11 en Sistema.
- Centro operativo en Inicio.

## No modifica
- Reglas de reservas.
- Cargos.
- Invitados.
- Cierre/reapertura.
- Estructura PostgreSQL crítica.

## Checklist previo
- `python -m py_compile main.py` OK.
- Versión actualizada en main, VERSION.txt y metadata.
