# -*- coding: utf-8 -*-

from odoo import models, fields,api
from datetime import date, datetime, timedelta

class HRContactType(models.Model):
    _inherit = 'hr.contract.type'

    #necesario para el mintra
    code = fields.Char(string='Código', required=True)

    #reemplazar el metodo para obtener el nombre del registro

    def name_get(self):
        res = []
        for record in self:
            res.append((record.id, '%s - %s' % (record.code if record.code else '', record.name if record.name else '')))
        return res