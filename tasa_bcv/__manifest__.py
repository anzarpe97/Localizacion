{
    'name': 'Tasa BCV',
    'version': '1.0',
    'summary': 'Actualización automática de la tasa de cambio desde el BCV',
    'author': 'Aecas',
    'category': 'Accounting',
    'depends': ['base'],
    'data': [
        'data/ir_cron_data.xml',
        'views/res_currency_view.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
