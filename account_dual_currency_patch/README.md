# account_dual_currency_patch

Parche para `account_dual_currency`:
- Crear facturas sin tasa (`tax_today` vacío).
- Recalcular montos USD al hacer `write()` cuando se proporcione `tax_today`.
- Evita recursividad con contexto `skip_usd_recompute`.

Instalación:
1. Copiar la carpeta al `addons_path`.
2. Reiniciar Odoo.
3. Actualizar lista de apps e instalar `Account Dual Currency - Patch: recompute USD on write`.

Pruebas sugeridas:
- Crear factura en draft (VEF). Ver que `tax_today` esté vacío y montos USD = 0.
- Hacer `write({'tax_today': 218.17})` y verificar que `amount_total_usd == amount_total / 218.17`.
- Cambiar líneas y guardar; verificar recompute con la tasa actual.
