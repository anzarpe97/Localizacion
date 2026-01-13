# account_dual_currency_patch/__manifest__.py
{
    "name": "Account Dual Currency - Patch: recompute USD on write",
    "version": "1.0.0",
    "summary": "Parchea account_dual_currency: crear sin tasa y recomputar USD al write",
    "description": """Crea facturas sin tasa (tax_today vacío) y recalcula montos USD
                     al hacer write cuando tax_today existe. Evita recursividad.""",
    "author": "Aecas / Assistant",
    "category": "Accounting",
    "depends": ["account", "account_dual_currency"],
    "data": [],
    "installable": True,
    "application": False,
    "license": "LGPL-3",
}
