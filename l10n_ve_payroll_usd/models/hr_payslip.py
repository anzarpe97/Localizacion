# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.tools import is_html_empty, html2plaintext
import base64
import logging
from datetime import datetime, timedelta
import calendar
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

class HRPayslip(models.Model):
    _inherit = 'hr.payslip'

    apuntes_contables = fields.One2many(related='move_id.line_ids', readonly=True)
    lunes_mes = fields.Integer(store=True, compute='_calcular_lunes', string="Lunes del mes")
    lunes_periodo = fields.Integer(store=True, compute='_calcular_lunes', string="Lunes del periodo")
    wage = fields.Monetary(store=True, related='contract_id.wage', string="Salario Mensual ")
    wage_ref = fields.Monetary(store=True, readonly=True, related='contract_id.wage_ref', string="Salario Mensual (REF)")
    wage_diario = fields.Float(store=True, readonly=True, compute="_wage_diario", string="Sueldo Diario ")
    wage_diario_ref = fields.Float(store=True, readonly=True, compute="_wage_diario_ref", string="Salario Diario (REF)")
    complemento = fields.Monetary(store=True, readonly=True, related='contract_id.complemento')
    tasa_cambio = fields.Float(store=True, string="Tasa de Cambio", default=lambda self: self._get_default_tasa_cambio())
    resultado_incentivo_manual = fields.Boolean(default=True)
    adelanto_manual = fields.Boolean(default=True)
    adelanto = fields.Float(string="Adelanto quincenal", store=True, readonly=False, compute="_adelanto")
    pestaciones_id = fields.Many2one('hr.employee.prestaciones', string="Prestaciones Sociales")
    installment_ids = fields.Many2many('hr.employee.loan.installment.line', string='Cuotas de Préstamos')
    installment_amount = fields.Float('Monto de Cuotas', compute='get_installment_amount')
    installment_int = fields.Float('Monto Intereses', compute='get_installment_amount')
    sign_request_id = fields.Many2one('sign.request', string='Solicitud de Firma')
    pdf_signed = fields.Boolean(string='PDF Firmado', copy=False, default=False)

    def action_payslip_cancel(self):
        res = super(HRPayslip, self).action_payslip_cancel()
        for rec in self:
            if rec.pestaciones_id:
                rec.pestaciones_id.unlink()
            if rec.struct_id.id == self.env.ref('l10n_ve_payroll_usd.structure_vacaciones').id:
                vacaciones = self.env['hr.employee.vacaciones'].search([('employee_id', '=', rec.employee_id.id),
                                                                         ('anio', '=', rec.date_from.year)])
                dias_vaca = rec.worked_days_line_ids.filtered(lambda x: x.code == 'VACA')
                if vacaciones:
                    if dias_vaca:
                        vacaciones.dias_vaca -= dias_vaca.number_of_days
        return res

    @api.model
    def create(self, vals):
        result = super(HRPayslip, self).create(vals)
        for rec in result:
            if rec.payslip_run_id:
                rec.tasa_cambio = rec.payslip_run_id.tasa_cambio
        return result

    @api.depends('date_to', 'date_from')
    def _calcular_lunes(self):
        for record in self:
            contador = 0
            formato = "%d/%m/%Y"
            adesde = record.date_from.year
            mdesde = record.date_from.month
            fechadesde = f"1/{mdesde}/{adesde}"
            ahasta = record.date_to.year
            mhasta = record.date_to.month
            monthRange = calendar.monthrange(ahasta, mhasta)
            fechahasta = f"{monthRange[1]}/{mhasta}/{ahasta}"
            fechadesded = datetime.strptime(fechadesde, formato)
            fechahastad = datetime.strptime(fechahasta, formato)
            while fechadesded <= fechahastad:
                if datetime.weekday(fechadesded) == 0:
                    contador += 1
                fechadesded += timedelta(days=1)
            record.lunes_mes = contador

            contador = 0
            fechadesded = record.date_from
            fechahastad = record.date_to
            while fechadesded <= fechahastad:
                if datetime.weekday(fechadesded) == 0:
                    contador += 1
                fechadesded += timedelta(days=1)
            record.lunes_periodo = contador

    @api.onchange('struct_id')
    def _struct_id_change(self):
        for rec in self:
            otras_entradas = [(5, 0, 0)]
            for o in rec.struct_id.input_line_type_ids:
                if o.monstar_automatico:
                    otras_entradas.append((0, 0, {'input_type_id': o.id}))
            rec.input_line_ids = otras_entradas

    @api.depends('wage')
    def _wage_diario(self):
        for record in self:
            record["wage_diario"] = record.wage / 30

    @api.depends('wage_ref')
    def _wage_diario_ref(self):
        for record in self:
            record["wage_diario_ref"] = record.wage_ref / 30

    @api.onchange('worked_days_line_ids')
    def _actualizar_tabla(self):
        struct_vaca_id = self.env.ref('l10n_ve_payroll_usd.structure_vacaciones').id
        for rec in self:
            if rec.worked_days_line_ids and rec.struct_id.id == struct_vaca_id:
                pass

    @api.depends('employee_id', 'date_from', 'date_to')
    def _adelanto(self):
        for rec in self:
            monto_adelanto = 0
            rec.adelanto_manual = True
            if rec.employee_id and rec.date_from and rec.date_to:
                dominio = [('code', '=', 'ADE'), ('employee_id', '=', rec.employee_id.id), ('date_from', '>=', rec.date_from),
                           ('date_to', '<=', rec.date_to)]
                if rec.number:
                    dominio.append(('slip_id.number', '!=', rec.number))
                adelantos = rec.env['hr.payslip.line'].search(dominio)
                for i in adelantos:
                    if i.slip_id != rec.id:
                        monto_adelanto += i.amount
                        rec.adelanto_manual = False
            rec.adelanto = monto_adelanto

    def _get_default_tasa_cambio(self):
        moneda = self.env.company.currency_id_dif
        tasa = moneda.rate
        for rec in self:
            if rec.payslip_run_id and rec.payslip_run_id.tasa_cambio > 0:
                tasa = rec.payslip_run_id.tasa_cambio
        return tasa

    @api.onchange('tasa_cambio')
    def _tasa_cambio_change(self):
        for pl in self:
            for w in pl.worked_days_line_ids:
                w._amount_ref()

    def compute_sheet(self):
        for rec in self:
            installment_ids = self.env['hr.employee.loan.installment.line'].search(
                [('employee_id', '=', rec.employee_id.id), ('loan_id.state', '=', 'done'),
                 ('is_paid', '=', False), ('date', '<=', rec.date_to)])
            if installment_ids:
                rec.installment_ids = [(6, 0, installment_ids.ids)]
            if len(self.worked_days_line_ids) > 0:
                self._actualizar_tabla()
        res = super(HRPayslip, self).compute_sheet()
        return res

    def _prepare_line_values(self, line, account_id, date, debit, credit):
        res = super(HRPayslip, self)._prepare_line_values(line, account_id, date, debit, credit)
        res['partner_id'] = self._get_partner_id(line.salary_rule_id)
        # if debit > 0:
        #     res['debit_ref'] = line.total_ref
        #     res['credit_ref'] = 0
        # if credit > 0:
        #     res['credit_ref'] = line.total_ref
        #     res['debit_ref'] = 0
        return res

    def _get_partner_id(self, salary_rule_id):
        if salary_rule_id.origin_partner == 'empleado':
            return self.employee_id.address_home_id.id
        elif salary_rule_id.origin_partner == 'empresa':
            return self.company_id.partner_id.id
        elif salary_rule_id.origin_partner == 'ivss':
            return self.company_id.ivss_id.id
        elif salary_rule_id.origin_partner == 'banavih':
            return self.company_id.banavih_id.id
        elif salary_rule_id.origin_partner == 'otro':
            return salary_rule_id.partner_id.id

    @api.depends('tasa_cambio', 'sal_mensual')
    def _sal_mensual_ref(self):
        for record in self:
            if record.tasa_cambio > 0:
                record["sal_mensual_ref"] = record.sal_mensual * record.tasa_cambio

    @api.depends('tasa_cambio')
    def _complemento_mensual_bs(self):
        for record in self:
            if record.tasa_cambio > 0:
                record["complemento_mensual_bs"] = record.complemento_mensual * record.tasa_cambio

    @api.onchange('complemento_mensual')
    def _complemento_mensual_change(self):
        for record in self:
            if record.tasa_cambio > 0:
                record["complemento_mensual_bs"] = record.complemento_mensual * record.tasa_cambio

    @api.depends('complemento_mensual')
    def _complemento_diario(self):
        for record in self:
            record["complemento_diario"] = record.complemento_mensual / 30

    @api.depends('complemento_mensual_bs')
    def _complemeto_diario_bs(self):
        for record in self:
            record["complemento_diario_bs"] = record.complemento_mensual_bs / 30

    import logging

    def _create_account_move(self, values):
        for rec in self:
            if isinstance(values, list):
                for l in values:
                    if self.env['ir.module.module'].search(
                            [('name', '=', 'account_dual_currency'), ('state', '=', 'installed')]):
                        l['tax_today'] = rec.tasa_cambio
                    
                    # para todas las line_ids en values sumar los debitos y creditos
                    # si el debito es mayor que el credito entonces crear una linea con el monto de la diferencia
                    # si el credito es mayor que el debito entonces crear una linea con el monto de la diferencia
                    # si el debito es igual al credito entonces no crear linea
                    debito = 0
                    debito_ref = 0
                    credito = 0
                    credito_ref = 0
                    journal_id = self.env['account.journal'].browse(l['journal_id'])
                    default_account = journal_id.default_account_id
                    
                    for line in l['line_ids']:
                        debito += line[2].get('debit', 0)  # Usar get para evitar KeyError
                        # debito_ref += line[2].get('debit_ref', 0)  # Descomentado si es necesario
                        credito += line[2].get('credit', 0)  # Usar get para evitar KeyError
                        # credito_ref += line[2].get('credit_ref', 0)  # Descomentado si es necesario
                    
                    diferencia = debito - credito
                    # diferencia_ref = debito_ref - credito_ref  # Descomentado si es necesario
                    diferencia = round(diferencia, rec.company_id.currency_id.decimal_places)
                    # diferencia_ref = round(diferencia_ref, rec.company_id.currency_id_dif.decimal_places)  # Descomentado si es necesario
                    
                    if diferencia > 0:
                        l['line_ids'].append((0, 0, {
                            'name': 'Diferencia',
                            'account_id': default_account.id,
                            'debit': 0,
                            # 'debit_ref': 0,  # Descomentado si es necesario
                            'credit': abs(diferencia),
                            # 'credit_ref': abs(diferencia_ref),  # Descomentado si es necesario
                        }))
                    elif diferencia < 0:
                        l['line_ids'].append((0, 0, {
                            'name': 'Diferencia',
                            'account_id': default_account.id,
                            'debit': abs(diferencia),
                            # 'debit_ref': abs(diferencia_ref),  # Descomentado si es necesario
                            'credit': 0,
                            # 'credit_ref': 0,  # Descomentado si es necesario
                        }))
            else:
                # verificar si esta instalado la account_dual_currency
                if self.env['ir.module.module'].search([('name', '=', 'account_dual_currency'), ('state', '=', 'installed')]):
                    values['tax_today'] = rec.tasa_cambio
                
                # para todas las line_ids en values sumar los debitos y creditos
                # si el debito es mayor que el credito entonces crear una linea con el monto de la diferencia
                # si el credito es mayor que el debito entonces crear una linea con el monto de la diferencia
                # si el debito es igual al credito entonces no crear linea
                debito = 0
                debito_ref = 0
                credito = 0
                credito_ref = 0
                journal_id = self.env['account.journal'].browse(values['journal_id'])
                default_account = journal_id.default_account_id
                
                for l in values['line_ids']:
                    debito += l[2].get('debit', 0)  # Usar get para evitar KeyError
                    # debito_ref += l[2].get('debit_ref', 0)  # Descomentado si es necesario
                    credito += l[2].get('credit', 0)  # Usar get para evitar KeyError
                    # credito_ref += l[2].get('credit_ref', 0)  # Descomentado si es necesario
                
                diferencia = debito - credito
                # diferencia_ref = debito_ref - credito_ref  # Descomentado si es necesario
                diferencia = round(diferencia, rec.company_id.currency_id.decimal_places)
                # diferencia_ref = round(diferencia_ref, rec.company_id.currency_id_dif.decimal_places)  # Descomentado si es necesario
                
                if diferencia > 0:
                    values['line_ids'].append((0, 0, {
                        'name': 'Diferencia',
                        'account_id': default_account.id,
                        'debit': 0,
                        # 'debit_ref': 0,  # Descomentado si es necesario
                        'credit': abs(diferencia),
                        # 'credit_ref': abs(diferencia_ref),  # Descomentado si es necesario
                    }))
                elif diferencia < 0:
                    values['line_ids'].append((0, 0, {
                        'name': 'Diferencia',
                        'account_id': default_account.id,
                        'debit': abs(diferencia),
                        # 'debit_ref': abs(diferencia_ref),  # Descomentado si es necesario
                        'credit': 0,
                        # 'credit_ref': 0,  # Descomentado si es necesario
                    }))

        return self.env['account.move'].sudo().create(values)


    def action_payslip_done(self):
        res = super(HRPayslip, self).action_payslip_done()
        for rec in self:
            if rec.struct_id.procesar_prestaciones:
                rec.procesar_prestaciones()
            if rec.struct_id.id == self.env.ref('l10n_ve_payroll_usd.structure_vacaciones').id:
                vacaciones = self.env['hr.employee.vacaciones'].search([('employee_id', '=', rec.employee_id.id),
                                                                         ('anio', '=', rec.date_from.year)])
                dias_vaca = rec.worked_days_line_ids.filtered(lambda x: x.code == 'VACA')
                if vacaciones:
                    if dias_vaca:
                        vacaciones.dias_vaca += dias_vaca.number_of_days
                else:
                    if dias_vaca:
                        data = {'employee_id': rec.employee_id.id, 'anio': rec.date_from.year, 'dias_vaca': dias_vaca.number_of_days,
                                'company_id': rec.company_id.id}
                        self.env['hr.employee.vacaciones'].create(data)
            if rec.installment_ids:
                for installment in rec.installment_ids:
                    if not installment.is_skip:
                        installment.is_paid = True
                    installment.payslip_id = rec.id
        return res

    def procesar_prestaciones(self):
        for rec in self:
            if rec.date_to.day >= 28:
                if rec.company_id.periodo_prestaciones == 'trimestral' and rec.date_to.month not in [3, 6, 9, 12]:
                    continue  # Saltar meses que no cierran trimestre

                mes_operacion = rec.date_to.month
                anio = rec.date_to.year
                dias_abonados = 0
                dias_adicional = 0

                verificar = self.env['hr.employee.prestaciones'].search([
                    ('employee_id', '=', rec.employee_id.id),
                    ('anio', '=', anio),
                    ('mes_opera', '=', mes_operacion)
                ])

                if not verificar:
                    employee_id = rec.employee_id.id
                    salario_base = 0
                    salario_base_diario = 0
                    salario_integral = 0
                    salario_integral_diario = 0
                    mes_cump = 1

                    fecha_inicio_mes = datetime(anio, mes_operacion, 1)
                    fecha_fin_mes = datetime(anio, mes_operacion, calendar.monthrange(anio, mes_operacion)[1])

                    category_hr_payroll_BASIC = self.env.ref('hr_payroll.BASIC').id
                    category_hr_payroll_SUBS = self.env.ref('l10n_ve_payroll_usd.category_asignacion_subsidio').id

                    payslip_line = self.env['hr.payslip.line'].search([
                        ('category_id', 'in', [category_hr_payroll_BASIC, category_hr_payroll_SUBS]),
                        ('slip_id.date_from', '>=', fecha_inicio_mes),
                        ('slip_id.date_to', '<=', fecha_fin_mes),
                        ('employee_id', '=', employee_id),
                        ('slip_id.struct_id.procesar_prestaciones', '=', True)
                    ])

                    line_ADEP = self.env['hr.payslip.line'].search([
                        ('code', '=', 'ADEP'),
                        ('slip_id.date_from', '>=', fecha_inicio_mes),
                        ('slip_id.date_to', '<=', fecha_fin_mes),
                        ('employee_id', '=', employee_id)
                    ])

                    adelanto_prestaciones = sum(line_ADEP.mapped('total')) if line_ADEP else 0

                    if payslip_line:
                        salario_base = rec.contract_id.wage_ref
                        salario_base_diario = salario_base / 30

                        utilidades_fracionadas = (salario_base_diario * rec.contract_id.dias_utilidades) / 360
                        vacaciones_fracionadas = (salario_base_diario * rec.contract_id.dias_provision_vaca) / 360

                        salario_integral = salario_base_diario + utilidades_fracionadas + vacaciones_fracionadas

                        if rec.company_id.periodo_prestaciones == 'mensual':
                            dias_abonados = 5
                            mes_cump = 1
                        else:  # Trimestral
                            meses_incluidos = self.env['hr.employee.prestaciones'].search([
                                ('employee_id', '=', rec.employee_id.id),
                                ('anio', '=', anio),
                                ('dias_abonados', '>', 0)
                            ], order='mes_opera asc', limit=1)

                            if meses_incluidos:
                                mes_cump = meses_incluidos.mes_cump + 1
                                if (meses_incluidos.mes_cump / 3).is_integer():
                                    dias_abonados = 15
                                else:
                                    dias_abonados = 0
                                anios_cumplidos = int(meses_incluidos.mes_cump / 12)
                                dias_adicional = 0
                                if anios_cumplidos > 2:
                                    dias_adicional = 2 * (anios_cumplidos - 2)
                                    dias_adicional = min(dias_adicional, 30)
                            else:
                                dias_abonados = 15
                                mes_cump = 3

                    if salario_integral > 0:
                        company_id = rec.company_id.id
                        currency_id = rec.company_id.currency_id.id

                        monto_presta = salario_integral * dias_abonados
                        monto_adici = salario_integral * dias_adicional

                        # Buscar la tasa de interés vigente
                        tasa = self.env['hr.prestaciones.interes'].search(
                            [('fecha_vigencia', '<=', fields.Date.today())],
                            order='fecha_vigencia desc',
                            limit=1
                        )
                        tasa_interes = tasa.tasa_interes if tasa else 0.0

                        monto_interes = ((monto_presta + monto_adici) * (tasa_interes / 100.0) / 12)

                        # Buscar el último registro de prestaciones acumuladas
                        ultimo_registro = self.env['hr.employee.prestaciones'].search([
                            ('employee_id', '=', employee_id)
                        ], order="anio desc, mes_opera desc", limit=1)

                        # Inicializar acumulados
                        monto_prestaciones_acumulado = monto_presta
                        monto_interes_acumulado = 0.0
                        monto_total_anterior = 0.0
                        monto_presta_acumulado_anterior = 0.0
                        dias_acumulados = 0.00

                        if ultimo_registro:
                            monto_presta_acumulado_anterior = ultimo_registro.monto_presta_acumulado
                            monto_prestaciones_acumulado += monto_presta_acumulado_anterior
                            monto_interes_acumulado = ultimo_registro.monto_interes_acumulado
                            monto_total_anterior = ultimo_registro.monto_total
                            dias_acumulados = ultimo_registro.dias_acumulados  # <-- aquí el cambio

                        # Calcular interés sobre monto acumulado anterior (no sobre el actual)
                        monto_interes = monto_presta_acumulado_anterior * (tasa_interes / 100.0) / 12
                        monto_interes_acumulado += monto_interes
                        
                        #Acumulado de días abonados.
                        dias_acumulados += dias_abonados

                        # Calcular el total acumulado general
                        monto_total = monto_total_anterior + monto_presta + monto_adici + monto_interes


                        data = {
                            'employee_id': employee_id,
                            'anio': anio,
                            'mes_cump': mes_cump,
                            'mes_opera': mes_operacion,
                            'salario_base': salario_base,
                            'salario_base_diario': salario_base_diario,
                            'salario_integral': salario_integral,
                            'dias_abonados': dias_abonados,
                            'dias_acumulados': dias_acumulados,
                            'dias_adici': dias_adicional,
                            'monto_presta': monto_presta,
                            'monto_adici': monto_adici,
                            'tasa_interes': tasa_interes,
                            'monto_interes': monto_interes,
                            'monto_interes_acumulado': monto_interes_acumulado,
                            'monto_retiro': adelanto_prestaciones,
                            'monto_presta_acumulado': monto_prestaciones_acumulado,
                            'monto_total': monto_total,
                            'company_id': company_id,
                            'currency_id': currency_id,
                        }

                        presta_id = self.env['hr.employee.prestaciones'].create(data)
                        if presta_id:
                            rec.pestaciones_id = presta_id.id
                            rec.message_post(body="Se ha generado el registro de prestaciones sociales para el empleado %s" % rec.employee_id.name)

    def _is_invalid(self):
        self.ensure_one()
        if self.state not in ['done', 'paid']:
            return _("La nómina debe estar en estado 'Hecha' o 'Pagada' para poder imprimir el recibo de pago.")
        return False

    def get_worked_days_data(self, payslip):
        worked_days = {
            'AUSE': {'number_of_days': 0},
            'AUSEP': {'number_of_days': 0},
            'VACA': {'number_of_days': 0},
            'DDFVACA': {'number_of_days': 0},
            'DDESS': {'number_of_days': 0},
            'DDESST': {'number_of_days': 0},
            'DDESD': {'number_of_days': 0},
            'DDESDT': {'number_of_days': 0},
            'FERI': {'number_of_days': 0},
            'FERIT': {'number_of_days': 0},
            'HED': {'number_of_days': 0},
            'HEN': {'number_of_days': 0},
            # Agrega otras claves según sea necesario
        }
        for wd in payslip.worked_days_line_ids:
            if wd.code in worked_days:
                worked_days[wd.code]['number_of_days'] = wd.number_of_days
        return worked_days

    def _get_payslip_lines(self):
        line_vals = []
        for payslip in self:
            if not payslip.contract_id:
                raise UserError(_("There's no contract set on payslip %s for %s. Check that there is at least a contract set on the employee form.", payslip.name, payslip.employee_id.name))
            localdict = self.env.context.get('force_payslip_localdict', None) or payslip._get_localdict()
            rules_dict = localdict['rules']
            result_rules_dict = localdict['result_rules']
            blacklisted_rule_ids = self.env.context.get('prevent_payslip_computation_line_ids', [])
            result = {}
            worked_days_data = self.get_worked_days_data(payslip)  # Obtener los datos de worked_days
            localdict.update({'worked_days': worked_days_data})  # Actualizar el diccionario local
            for rule in sorted(payslip.struct_id.rule_ids, key=lambda x: x.sequence):
                if rule.id in blacklisted_rule_ids:
                    continue
                localdict.update({'result': None, 'result_qty': 1.0, 'result_rate': 100, 'result_name': False})
                if rule._satisfy_condition(localdict):
                    employee_lang = payslip.employee_id.sudo().address_home_id.lang
                    context = {'lang': employee_lang}
                    if rule.code in localdict['same_type_input_lines']:
                        for multi_line_rule in localdict['same_type_input_lines'][rule.code]:
                            localdict['inputs'][rule.code] = multi_line_rule
                            amount, qty, rate = rule._compute_rule(localdict)
                            tot_rule = amount * qty * rate / 100.0
                            localdict = rule.category_id._sum_salary_rule_category(localdict, tot_rule)
                            rule_name = payslip._get_rule_name(localdict, rule, employee_lang)
                            line_vals.append({'sequence': rule.sequence, 'code': rule.code, 'name': rule_name, 'salary_rule_id': rule.id, 'contract_id': localdict['contract'].id, 'employee_id': localdict['employee'].id, 'amount': amount, 'quantity': qty, 'rate': rate, 'slip_id': payslip.id})
                    else:
                        amount, qty, rate = rule._compute_rule(localdict)
                        previous_amount = 0.0
                        tot_rule = amount * qty * rate / 100.0
                        localdict[rule.code] = tot_rule
                        result_rules_dict[rule.code] = {'total': tot_rule, 'amount': amount, 'quantity': qty}
                        rules_dict[rule.code] = rule
                        localdict = rule.category_id._sum_salary_rule_category(localdict, tot_rule - previous_amount)
                        rule_name = payslip._get_rule_name(localdict, rule, employee_lang)
                        result[rule.code] = {'sequence': rule.sequence, 'code': rule.code, 'name': rule_name, 'salary_rule_id': rule.id, 'contract_id': localdict['contract'].id, 'employee_id': localdict['employee'].id, 'amount': amount, 'quantity': qty, 'rate': rate, 'slip_id': payslip.id}
            line_vals += list(result.values())
        return line_vals

    @api.depends('installment_ids')
    def get_installment_amount(self):
        for payslip in self:
            amount = sum(installment.installment_amt for installment in payslip.installment_ids if not installment.is_skip)
            int_amount = sum(installment.ins_interest for installment in payslip.installment_ids)
            payslip.installment_amount = amount
            payslip.installment_int = int_amount

    @api.onchange('employee_id')
    def onchange_employee(self):
        if self.employee_id:
            installment_ids = self.env['hr.employee.loan.installment.line'].search([('employee_id', '=', self.employee_id.id), ('loan_id.state', '=', 'done'), ('is_paid', '=', False), ('date', '<=', self.date_to)])
            if installment_ids:
                self.installment_ids = [(6, 0, installment_ids.ids)]

    @api.onchange('installment_ids')
    def onchange_installment_ids(self):
        if self.employee_id:
            installment_ids = self.env['hr.employee.loan.installment.line'].search([('employee_id', '=', self.employee_id.id), ('loan_id.state', '=', 'done'), ('is_paid', '=', False), ('date', '<=', self.date_to)])
            if installment_ids:
                self.installment_ids = [(6, 0, installment_ids.ids)]

    def send_to_sign(self):
        for rec in self:
            if rec.sign_request_id:
                raise UserError(_("El recibo de pago %s ya ha sido enviado a firmar." % rec.number))
            if rec.pdf_signed:
                raise UserError(_("El recibo de pago %s ya ha sido firmado." % rec.number))
            if rec.employee_id.work_email:
                pdf = self.env['ir.actions.report'].with_context(lang=rec.employee_id.sudo().address_home_id.lang)._render_qweb_pdf(rec.struct_id.report_id, rec.id, data={'company_id': rec.company_id})[0]
                attachment_id = self.env['ir.attachment'].create({'name': rec.name, 'datas': base64.b64encode(pdf), 'res_model': 'hr.payslip', 'res_id': rec.id, 'type': 'binary'})
                template = self.env['sign.template'].create({'name': rec.name, 'tag_ids': [(6, 0, [self.env.ref('sign.sign_template_tag_1').id])], 'attachment_id': attachment_id.id, 'sign_item_ids': [(0, 0, {'name': 'Firma', 'responsible_id': self.env.ref('sign.sign_item_role_employee').id, 'type_id': self.env.ref('sign.sign_item_type_signature').id, 'page': 1, 'posX': 0.402, 'posY': 0.658, 'width': 0.2, 'height': 0.05, 'required': True})]})
                request = self.env['sign.request'].create({'reference': 'Nómina %s #%s - %s' % (rec.struct_id.name, rec.number, rec.employee_id.name), 'template_id': template.id, 'request_item_ids': [(0, 0, {'partner_id': rec.employee_id.address_home_id.id, 'access_via_link': True, 'role_id': self.env.ref('sign.sign_item_role_employee').id})], 'cc_partner_ids': [(4, rec.employee_id.address_home_id.id)]})
                rec.sign_request_id = request.id
            else:
                raise UserError(_("El usuario del empleado no tiene un correo electrónico configurado."))
