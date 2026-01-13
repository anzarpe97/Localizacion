{
    'name': 'Auditoría Fiscal SENIAT',
    'version': '17.0.1.0.1',
    'category': 'Accounting/Audit',
    'summary': 'Registro inmutable de actividad y usuario auditor SENIAT',
    'author': 'Aecas by Logica Cero',
    'depends': ['base', 'web', 'mail', 'account', 'sale', 'purchase', 'stock'],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'security/rules.xml',
        'data/seniat_user_data.xml',
        'data/audit_data.xml',
        'views/audit_log_views.xml',
        'views/audit_rule_views.xml',
        'views/menus.xml',
        'views/menu_patch.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'seniat_audit_compliance/static/src/js/connection_monitor.js',
        ],
    },
    'post_init_hook': 'post_init_hook',
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}