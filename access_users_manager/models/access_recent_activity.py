# -*- coding: utf-8 -*-
from odoo import fields, models, _
from datetime import datetime


class accessRecentActivityLine(models.Model):
    _name = 'recent.activity'
    _description = 'Users Login/Logout Activity'

    access_login_date = fields.Datetime('Fecha de Inicio de Sesión')
    access_logout_date = fields.Datetime('Fecha de Cierre de Sesión')
    access_duration = fields.Char('Duración')
    access_user_id = fields.Many2one('res.users', string='Usuarios')
    access_status = fields.Selection([('active', 'Activado'), ('close', 'Cerrado')], string='Estado')
    access_session_id = fields.Char(string='ID de la Sesión')

    def access_action_logout(self):
        """Admin can Logout to any user and evaluate time that how much time the user is activated."""
        for rec in self:
            rec.access_status = 'close'
            rec.access_logout_date = datetime.now()
            duration = datetime.now() - rec.access_login_date
            total_second = duration.seconds
            minute = total_second / 60
            hour = total_second > 3600
            day = duration.days
            if minute and not hour:
                rec.access_duration = str(int(minute)) + ' Minute'
            if hour and not day:
                hour = total_second / 3600
                minute = (total_second - int(hour) * 3600) / 60
                rec.access_duration = str(int(hour)) + ' Hour ' + str(int(minute)) + ' Minute'
            if day:
                hour = total_second
                if hour > 3600:
                    hour = hour / 3600
                    minutes = (total_second - (int(hour) * 3600)) / 60
                else:
                    hour = 0
                    minutes = hour / 60
                rec.access_duration = str(day) + ' Day ' + str(int(hour)) + ' Hour ' + str(int(minutes)) + ' Minute'
