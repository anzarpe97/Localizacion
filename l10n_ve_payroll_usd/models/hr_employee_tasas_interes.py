from odoo import models, fields

class HrPrestacionesInteres(models.Model):
    _name = 'hr.prestaciones.interes'
    _description = 'Tasa de Interés para Prestaciones'

    tasa_interes = fields.Float(string='Tasa de Interés', required=True)
    fecha_vigencia = fields.Date(string='Fecha de Vigencia', required=True)
