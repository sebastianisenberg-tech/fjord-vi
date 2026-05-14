# Release Checklist - Fjord VI 3.7.1.1

Checklist operativo mínimo para producción:

- VERSION.txt coincide con main.py y software_metadata.json
- Render levanta `uvicorn main:app`
- Templates críticos presentes
- Static críticos presentes
- DATABASE_URL configurado en producción
- Diagnóstico operativo en verde
- Backup SQL disponible
- Sin locks vencidos
