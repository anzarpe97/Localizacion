# -*- coding: utf-8 -*-

from odoo import models, fields,api,_

class HREmpleyeePrestaciones(models.Model):
    _name = 'hr.employee.prestaciones'
    _description = 'Prestaciones Sociales'

    employee_id = fields.Many2one('hr.employee', string='Empleado', required=True)
    anio = fields.Integer(string='Año', required=True)
    mes_cump = fields.Integer(string='Mes Cumplido', required=True)
    mes_opera = fields.Integer(string='Mes Operación', required=True)
    salario_base = fields.Float(string='Salario Base', required=True)
    salario_base_diario = fields.Float(string='Salario Base Diario', required=True)
    salario_integral = fields.Float(string='Salario Integral', required=True)
    dias_abonados = fields.Integer(string='Días Abonados', required=True)
    dias_acumulados = fields.Integer(string='Días Acumulados')
    dias_adici = fields.Integer(string='Días Adicional', default=0)
    dias_adici_acumulado = fields.Integer(string='Días Adicional Acumulados')

    monto_presta = fields.Float(string='Monto Prestaciones')
    monto_presta_acumulado = fields.Float(string='Monto Prestaciones Acumulado')

    monto_adici = fields.Float(string='Monto Adicional')
    monto_adici_acumulado = fields.Float(string='Monto Adicional Acumulado')

    monto_retiro = fields.Float(string='Monto Retiro')
    # monto_acumulado = fields.Float(string='Monto Acumulado')
    tasa_interes = fields.Float(string='Tasa de Interes')
    monto_interes = fields.Float(string='Monto Interes')
    monto_interes_acumulado = fields.Float(string='Monto Interes Acumulado')
    monto_total = fields.Float(string='Monto Total')

    company_id = fields.Many2one('res.company', string='Compañia', required=True, default=lambda self: self.env.company.id)
    currency_id = fields.Many2one('res.currency', string='Moneda', required=True, default=lambda self: self.env.company.currency_id.id)

    fecha_vigencia = fields.Date(string = "Fecha de Interés Vigente")

    @api.model
    def recalcular_acumulados(self):
        empleados = self.env['hr.employee'].search([])

        for empleado in empleados:
            acumulado_presta = 0
            acumulado_adici = 0
            acumulado_interes = 0

            registros = self.search([('employee_id', '=', empleado.id)], order="anio asc, mes_opera asc")
            for registro in registros:
                acumulado_presta += registro.monto_presta or 0
                acumulado_adici += registro.monto_adici or 0
                acumulado_interes += registro.monto_interes or 0

                registro.write({
                    'monto_presta_acumulado': acumulado_presta,
                    'monto_adici_acumulado': acumulado_adici,
                    'monto_interes_acumulado': acumulado_interes,
                })