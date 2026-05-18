# RC9.2 Captain Actions Safe

- Corrige el panel inferior de Capitán: los formularios clonados ahora se envían por POST nativo con delegación propia.
- Elimina ID duplicado `captainOpsSheet`, que podía volver impredecible el panel en móvil.
- `No embarca / sin cargo` vuelve a pedir motivo obligatorio también desde el panel clonado.
- Se evita que AJAX/global guards bloqueen acciones operativas críticas de Capitán.
- No modifica reglas de cierre ni liquidación.
