# -*- coding: utf-8 -*-
from odoo import api, Command, fields, models, tools

class HrWorkEntry(models.Model):
    _inherit = 'hr.work.entry'

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if 'work_entry_type_id' in vals:
                # Obtener las referencias de los tipos de entrada de trabajo
                work_entry_type_vaca = self.env.ref('l10n_ve_payroll_usd.work_entry_type_VACA', raise_if_not_found=False)
                work_entry_type_vaca_des_fer = self.env.ref('l10n_ve_payroll_usd.work_entry_type_VACA_des_fer', raise_if_not_found=False)

                if work_entry_type_vaca and vals['work_entry_type_id'] == work_entry_type_vaca.id:
                    date_start = vals.get('date_start')
                    if date_start:
                        date_start_obj = fields.Date.from_string(date_start)
                        # Verificar si es sábado (5) o domingo (6)
                        if date_start_obj.weekday() in [5, 6]:
                            if work_entry_type_vaca_des_fer:
                                vals['work_entry_type_id'] = work_entry_type_vaca_des_fer.id
        return super(HrWorkEntry, self).create(vals_list)
