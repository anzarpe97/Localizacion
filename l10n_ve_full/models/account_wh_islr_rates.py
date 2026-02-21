# coding: utf-8
from odoo import fields, models, api
from odoo.addons import decimal_precision as dp


class AccountWhIslrRates(models.Model):
    _name = 'account.wh.islr.rates'
    _description = 'Rates'

    name = fields.Char(string='Tasa',  size=256,
            help="Nombre de tasa de retención para los conceptos de la retención")
    code = fields.Char(
            'Código de concepto', size=3, required=True, help="Código Conceptual")
    base = fields.Float(
            'Sin importe de impuestos', required=True,
            help="Porcentaje de la cantidad sobre la cual aplicar la retención",
            digits=(16, 2))
    minimum= fields.Float(
            'Min. Cantidad', required=True,
          #  digits=(16, 2),
            help="Cantidad mínima, a partir de la cual determinará si esta"
                 "retenido")
    wh_perc= fields.Float(
            'Factor', required=True,
            digits=(16, 2),
            help="El porcentaje que se aplica a los ingresos imponibles sujetos a impuestos que arroja la"
                 "cantidad a retener")
    subtract= fields.Float(
            'Sustracción en unidades impositivas', required=True,
            digits=(16, 2),
            help="Cantidad a restar de la cantidad total a retener en UT. "
                 "Este sustraendo se multiplicará por el valor de la UT actual para obtener el monto en Bs",
            default=0.0)
    residence= fields.Boolean(
            'Residencia',
            help="Indica si una persona es residente, en comparación con la "
                 "dirección de la empresa")
    nature =fields.Boolean(
            'Natural', help="Indica si una persona es natural o Juridica")
    concept_id= fields.Many2one(
            'account.wh.islr.concept', 'Withhold  Concept', required=False,
            ondelete='cascade',
            help="Concepto de retención asociado a esta tasa")
    rate2 = fields.Boolean(
            'Tasa 2', help='Tasa utilizada para entidades extranjeras')

    def _get_name(self):
        """ Get the name of the withholding concept rate
        """
        res = {}
        for rate in self:
            if rate.nature:
                if rate.residence:
                    name = 'Persona' + ' ' + 'Natural' + ' ' + 'Residente'
                else:
                    name = 'Persona' + ' ' + 'Natural' + ' ' + 'No Residente'
            else:
                if rate.residence:
                    name = 'Persona' + ' ' + 'Juridica' + ' ' + 'Domiciliada'
                else:
                    name = 'Persona' + ' ' + 'Juridica' + ' ' + \
                        'No Domiciliada'
            res[rate.id] = name
        return res
    
    @api.onchange('minimum', 'name', 'wh_perc')
    def _onchange_minimum(self):
        """Actualiza el subtract cuando cambia el minimum o wh_perc"""
        if self.name == 'PJDO':
            # Para PJDO, el sustraendo generalmente es 0 o debe configurarse manualmente
            self.subtract = 0
        else:
            # Para PNRE y otros, el sustraendo en UT = minimum × (wh_perc / 100)
            if self.minimum > 0 and self.wh_perc > 0:
                self.subtract = self.minimum * (self.wh_perc / 100.0)
            else:
                self.subtract = 0
    
    def action_recalculate_subtract(self):
        """Método para recalcular el subtract de registros existentes"""
        for rec in self:
            if rec.name == 'PJDO':
                rec.subtract = 0
            else:
                if rec.minimum > 0 and rec.wh_perc > 0:
                    rec.subtract = rec.minimum * (rec.wh_perc / 100.0)
                else:
                    rec.subtract = 0
    
    @api.model
    def recalculate_all_subtracts(self):
        """Método para recalcular todos los subtracts de todos los registros"""
        all_rates = self.search([])
        for rate in all_rates:
            if rate.name == 'PJDO':
                rate.subtract = 0
            else:
                if rate.minimum > 0 and rate.wh_perc > 0:
                    rate.subtract = rate.minimum * (rate.wh_perc / 100.0)
                else:
                    rate.subtract = 0
        return True
    
    @api.model
    def create(self, vals):
        """Al crear un nuevo registro, calcular el subtract si no se proporciona"""
        if 'subtract' not in vals or vals.get('subtract', 0) == 0:
            # Calcular subtract basado en minimum y name
            name = vals.get('name', '')
            if name == 'PJDO':
                vals['subtract'] = 0
            else:
                minimum = vals.get('minimum', 0)
                wh_perc = vals.get('wh_perc', 0)
                if minimum > 0 and wh_perc > 0:
                    vals['subtract'] = minimum * (wh_perc / 100.0)
                else:
                    vals['subtract'] = 0
        return super(AccountWhIslrRates, self).create(vals)
