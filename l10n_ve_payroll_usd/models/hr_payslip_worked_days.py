# -*- coding: utf-8 -*-

from odoo import models, fields,api

class HRPayslipWorkedDays(models.Model):
    _inherit = 'hr.payslip.worked_days'

    @api.depends('amount','payslip_id.tasa_cambio')
    def _amount_ref(self):
        #tax_today_id = self.env['res.currency'].search([('name', '=', 'USD')])
        for record in self:
            if record.payslip_id:
                if record.payslip_id.tasa_cambio>0:
                    record.amount_ref = record.amount / record.payslip_id.tasa_cambio
                else:
                    record.amount_ref = record.amount
            else:
                record.amount_ref = record.amount


    amount_ref = fields.Float(string="Importe (REF)", compute="_amount_ref")
