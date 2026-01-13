# seniat_audit_compliance/hooks.py
import logging
from odoo import api, SUPERUSER_ID

_logger = logging.getLogger(__name__)

def post_init_setup_seniat_user(env):
    """
    Configuración SENIAT V.FINAL (Consolidada).
    Asegura permisos de lectura y visibilidad de menús, 
    incluyendo correcciones para flujo de Contabilidad (Account/Invoice group).
    """
    _logger.info(">>> INICIANDO CONFIGURACIÓN SENIAT (V.FINAL) <<<")
    
    # 1. SETUP BÁSICO
    main_company = env['res.company'].search([], limit=1, order='id asc')
    if not main_company: return

    # 2. OBTENER GRUPOS REQUERIDOS (Nativos y Custom)
    seniat_group = env.ref('seniat_audit_compliance.group_seniat_audit', raise_if_not_found=False)
    account_readonly_group = env.ref('account.group_account_readonly', raise_if_not_found=False)
    # GRUPO CLAVE PARA EL FLUJO DE ACCOUNT.MOVE (Contabilidad/Facturación)
    account_invoice_group = env.ref('account.group_account_invoice', raise_if_not_found=False)
    
    if not seniat_group: return

    # 3. ASIGNACIÓN DE GRUPOS AL USUARIO
    groups_to_add = [(4, seniat_group.id)]
    
    if account_readonly_group:
        groups_to_add.append((4, account_readonly_group.id))
    
    # [CRÍTICO] Se asigna el grupo de Facturación para que el flujo de account.move se complete
    if account_invoice_group:
        groups_to_add.append((4, account_invoice_group.id))
        _logger.info(">>> Grupo 'Contabilidad/Facturación' asignado para desbloquear el formulario.")

    # 4. CREAR/ACTUALIZAR USUARIO
    user_seniat = env['res.users'].with_context(active_test=False).search([('login', '=', 'seniat_auditor')], limit=1)
    
    if not user_seniat:
        user_seniat = env['res.users'].create({
            'name': 'Auditor SENIAT', 'login': 'seniat_auditor', 'password': 'seniat_venezuela_2025', 'active': True,
            'company_id': main_company.id, 'company_ids': [(4, main_company.id)],
            'groups_id': groups_to_add
        })
    else:
        user_seniat.write({'groups_id': groups_to_add})

    # 5. LISTA MAESTRA DE MODELOS A LEER
    models_to_read = {
        'Ventas_Core': [
            'sale.order', 'sale.order.line', 'res.partner', 'crm.team', 
            'sale.report', 'sale.payment.provider',
            'sale.order.spreadsheet', # Incluido el fix de la hoja de cálculo
            'utm.campaign', 'utm.source', 'utm.medium'
        ],
        'Dependencias_Sistema': [
            'uom.uom', 'uom.category', 'onboarding.onboarding', 'onboarding.onboarding.step',
            'res.currency', 'res.currency.rate', 'res.groups'
        ],
        'Contabilidad': [
            'account.move', 'account.payment', 'account.bank.statement', 'account.analytic.line'
        ],
        'Inventario': [
            'stock.picking', 'stock.picking.type', 'stock.quant', 
            'product.product', 'product.template', 'stock.move', 'stock.move.line', 'stock.location', 
            'stock.warehouse', 'stock.scrap', 'stock.lot'
        ],
        'Fabricacion_REFUERZO': [
            'mrp.production', 'mrp.bom', 'mrp.workorder', 'mrp.unbuild', 
            'mrp.routing.workcenter', 'mrp.workcenter'
        ],
        'Contactos': ['res.partner', 'res.users', 'res.company']
    }

    # 6. APLICAR ACLs (Lectura)
    for area, model_names in models_to_read.items():
        for model_name in model_names:
            model_record = env['ir.model'].search([('model', '=', model_name)], limit=1)
            
            if model_record:
                count = env['ir.model.access'].search_count([
                    ('group_id', '=', seniat_group.id),
                    ('model_id', '=', model_record.id)
                ])
                
                if count == 0:
                    env['ir.model.access'].create({
                        'name': f'access_seniat_{model_name.replace(".", "_")}',
                        'model_id': model_record.id,
                        'group_id': seniat_group.id,
                        'perm_read': True,
                        'perm_write': False,
                        'perm_create': False,
                        'perm_unlink': False
                    })

    # 7. INYECCIÓN DE MENÚS (Forzado)
    menus_to_force = [
        'account.menu_finance', 'sale.sale_menu_root', 'purchase.menu_purchase_root',
        'stock.menu_stock_root', 'contacts.menu_contacts', 'seniat_audit_compliance.audit_main_menu'
    ]

    for menu_xmlid in menus_to_force:
        menu = env.ref(menu_xmlid, raise_if_not_found=False)
        if menu:
            menu.write({'groups_id': [(4, seniat_group.id)]})

    _logger.info(">>> CONFIGURACIÓN SENIAT FINALIZADA <<<")