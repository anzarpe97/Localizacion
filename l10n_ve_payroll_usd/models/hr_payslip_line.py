from odoo import models, fields, api

class HRPayslipLine(models.Model):
    _inherit = 'hr.payslip.line'

    currency_id_dif = fields.Many2one("res.currency", string="Referencia en Divisa", default=lambda self: self.env.company.currency_id_dif)
    total_ref = fields.Monetary(store=True, readonly=True, compute="_total_ref", string="Total (REF)", default=0, currency_field='currency_id_dif')
    total = fields.Monetary(string='Total', compute='_compute_totals', store=True)

    amount = fields.Float(string='Importe', digits=(16, 6), store=True)  # Mantén la precisión completa
    currency_id = fields.Many2one('res.currency', string='Moneda')

    dias = fields.Char(compute='_compute_dias', store=True, string="Días")
    horas = fields.Char(compute='_compute_dias', store=True, string="Horas")

    department_id = fields.Many2one('hr.department', string='Departamento', related='employee_id.department_id', store=True)
    struct_id = fields.Many2one('hr.payroll.structure', string='Estructura', related='slip_id.struct_id', store=True)

    @api.model
    def create(self, vals):
        if 'currency_id' not in vals:
            vals['currency_id'] = self.env.user.company_id.currency_id.id
        return super(HRPayslipLine, self).create(vals)

    @api.depends('total', 'slip_id.tasa_cambio')
    def _total_ref(self):
        for record in self:
            if record.slip_id.tasa_cambio > 0:
                record.total_ref = round(record.amount * record.slip_id.tasa_cambio, 15)
            else:
                record.total_ref = 0
            record.total = record.amount

    @api.depends('name', 'total_ref', 'salary_rule_id', 'slip_id.contract_id.anios_antiguedad')
    def _compute_dias(self):
        for rec in self:
            valor_dias = ""
            valor_horas = ""
            worked_days_line_ids = rec.slip_id.worked_days_line_ids
            
            # Cálculo especial para ADIVACA y ADIBONOVACA
            if rec.code == 'ADIVACA':
                if rec.slip_id.contract_id.anios_antiguedad <= 1:
                    valor_dias = rec.slip_id.contract_id.anios_antiguedad - 1
                else:
                    valor_dias = rec.slip_id.contract_id.anios_antiguedad
            elif rec.code == 'GPSAB':
                prestaciones = self.env['hr.employee.prestaciones'].search(
                    [('employee_id', '=', rec.slip_id.employee_id.id)],
                    order='create_date desc',
                    limit=1
                )
                valor_dias = prestaciones.dias_acumulados + prestaciones.dias_adici_acumulado if prestaciones else 0
            elif rec.code == 'GPSC':
                prestaciones = self.env['hr.employee.prestaciones'].search(
                    [('employee_id', '=', rec.slip_id.employee_id.id)],
                    order='create_date desc',
                    limit=1
                )
                valor_dias = prestaciones.dias_adici_acumulado if prestaciones else 0
            elif rec.code == 'VACAV':
                if rec.contract_id.anios_antiguedad > 0:
                    valor_dias = rec.slip_id.contract_id.anios_antiguedad + 15
                else:
                    valor_dias = 0
            elif rec.code == 'BONOVACAV':
                if rec.contract_id.anios_antiguedad > 0:
                    valor_dias = rec.slip_id.contract_id.anios_antiguedad + 16
                else:
                    valor_dias = 0
            elif rec.code == 'VACAF':
                if rec.contract_id.anios_antiguedad > 0:
                    valor_dias = rec.slip_id.x_studio_dias_de_vacaciones_no_disfrutados + 15
                else:
                    hoy = rec.slip_id.date_to
                    fecha_ingreso = rec.contract_id.date_start

                    if hoy and fecha_ingreso:
                        anios_antiguedad = rec.contract_id.anios_antiguedad

                        if anios_antiguedad > 0:
                            mes_actual = hoy.month
                        else:
                            mes_actual = hoy.month - fecha_ingreso.month
                            if mes_actual < 0:
                                mes_actual = 0  # Evitar meses negativos si está en el mismo año y mes de ingreso futuro

                        valor_dias = ((15 + anios_antiguedad) / 12) * mes_actual
            elif rec.code == 'BONOVACAF':
                if rec.contract_id.anios_antiguedad > 0:
                    valor_dias = rec.slip_id.x_studio_bono_vacacional_no_disfrutado + 16
                else:
                    hoy = rec.slip_id.date_to
                    fecha_ingreso = rec.contract_id.date_start

                    if hoy and fecha_ingreso:
                        anios_antiguedad = rec.contract_id.anios_antiguedad

                        if anios_antiguedad > 0:
                            mes_actual = hoy.month
                        else:
                            mes_actual = hoy.month - fecha_ingreso.month
                            if mes_actual < 0:
                                mes_actual = 0  # Evitar meses negativos si está en el mismo año y mes de ingreso futuro

                        valor_dias = ((16 + anios_antiguedad) / 12) * mes_actual
            elif rec.code == 'UTILIDF':
                hoy = rec.slip_id.date_to
                fecha_ingreso = rec.contract_id.date_start

                if hoy and fecha_ingreso:
                    anios_antiguedad = rec.contract_id.anios_antiguedad

                    if anios_antiguedad > 0:
                        mes_actual = hoy.month
                    else:
                        mes_actual = hoy.month - fecha_ingreso.month
                        if mes_actual < 0:
                            mes_actual = 0  # Evitar meses negativos si está en el mismo año y mes de ingreso futuro

                    valor_dias = (60 / 12) * mes_actual
                else:
                    valor_dias = 0
            elif rec.code == 'ADIBONOVACA':
                    valor_dias = rec.slip_id.contract_id.anios_antiguedad
            elif rec.code == 'BONOVACA':
                valor_dias = rec.slip_id.contract_id.dias_bono_vacacional
            elif rec.code == 'VACA':
                valor_dias = 15
            elif rec.code == 'DDFVACA':
                valor_dias = (
                    worked_days_line_ids.filtered(lambda x: x.code == 'DDFVACA').number_of_days
                )
            elif rec.code == 'DPSUELDO':
                valor_dias = (
                    worked_days_line_ids.filtered(lambda x: x.code == 'DDESS').number_of_days +
                    worked_days_line_ids.filtered(lambda x: x.code == 'DDESD').number_of_days
                )
            elif rec.category_id.code == 'BASIC':
                valor_dias = (
                    worked_days_line_ids.filtered(lambda x: x.code == 'WORK100').number_of_days +
                    worked_days_line_ids.filtered(lambda x: x.code == 'AUSEP').number_of_days
                )
            else:
                worked_days_line_ids = worked_days_line_ids.filtered(lambda x: x.code == rec.code)
                if rec.salary_rule_id.mostrar_cantidad == 'dias':
                    valor_dias = round(worked_days_line_ids.number_of_days, 2) if worked_days_line_ids else ""
                    valor_horas = ""
                elif rec.salary_rule_id.mostrar_cantidad == 'horas':
                    valor_horas = round(worked_days_line_ids.number_of_hours, 2) if worked_days_line_ids else ""
                    valor_dias = ""
                else:
                    valor_dias = ""
                    valor_horas = ""

            rec.dias = str(valor_dias)
            rec.horas = str(valor_horas)