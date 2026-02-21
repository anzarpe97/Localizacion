from . import models
from . import wizard
from . import report


def post_init_hook(cr, registry):
    """Hook ejecutado después de instalar/actualizar el módulo
    para recalcular todos los sustraendos ISLR existentes"""
    from odoo import api, SUPERUSER_ID
    
    env = api.Environment(cr, SUPERUSER_ID, {})
    # Recalcular todos los sustraendos
    env['account.wh.islr.rates'].recalculate_all_subtracts()


    #prueba
