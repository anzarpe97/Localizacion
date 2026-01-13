from odoo import models, fields

class AuditRule(models.Model):
    _name = 'audit.rule'
    _description = 'Reglas de Auditoría'

    name = fields.Char(related='model_id.name', string="Nombre Modelo")
    model_id = fields.Many2one('ir.model', string="Modelo a Auditar", required=True, ondelete='cascade')
    active = fields.Boolean(default=True, string="Auditoría Activa")
    
    _sql_constraints = [
        ('model_uniq', 'unique(model_id)', '¡Este modelo ya está configurado para auditoría!')
    ]