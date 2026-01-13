from odoo import models, fields, api, _
from odoo.exceptions import UserError
from datetime import timedelta

class AuditLog(models.Model):
    _name = 'audit.log'
    _description = 'Registro de Auditoría SENIAT'
    _order = 'create_date desc'

    name = fields.Char(string="Descripción", required=True, index=True)
    user_id = fields.Many2one('res.users', string="Usuario", default=lambda self: self.env.user, index=True)
    model_id = fields.Many2one('ir.model', string="Modelo", index=True)
    res_id = fields.Integer(string="ID Recurso")
    
    operation_type = fields.Selection([
        ('create', 'Creación'),
        ('write', 'Modificación'),
        ('unlink', 'Eliminación'),
        ('connection_lost', 'Pérdida de Conexión'),
        ('access_error', 'Acceso Fallido')
    ], string="Tipo de Evento", required=True, index=True)

    old_values = fields.Text(string="Valores Anteriores")
    new_values = fields.Text(string="Valores Nuevos/Detalles")
    
    ip_address = fields.Char(string="Dirección IP")
    
    def unlink(self):
        """ Inmutabilidad: Solo permitir borrado vía CRON del sistema """
        for rec in self:
            if self.env.user.id != self.env.ref('base.user_root').id:
                raise UserError(_("Por normativa SENIAT, los registros de auditoría son inmutables."))
        return super(AuditLog, self).unlink()

    @api.model
    def action_cleanup_old_logs(self):
        """ Método llamado por el Cron para limpiar logs antiguos """
        # Usamos fields.Datetime.now() que es el estándar de Odoo
        limit_date = fields.Datetime.now() - timedelta(days=90)
        # Ejecutamos el borrado como sudo para saltar reglas de seguridad si es necesario
        self.sudo().search([('create_date', '<', limit_date)]).unlink()
        return True