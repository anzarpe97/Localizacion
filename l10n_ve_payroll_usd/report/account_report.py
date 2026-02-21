# -*- coding: utf-8 -*-
import ast
import datetime
import io
import json
import logging
import math
import re
import base64
from ast import literal_eval
from collections import defaultdict
from functools import cmp_to_key

import markupsafe
from babel.dates import get_quarter_names
from dateutil.relativedelta import relativedelta

from odoo.addons.web.controllers.utils import clean_action
from odoo import models, fields, api, _, osv
from odoo.exceptions import RedirectWarning, UserError, ValidationError
from odoo.tools import config, date_utils, get_lang, float_compare, float_is_zero
from odoo.tools.float_utils import float_round
from odoo.tools.misc import formatLang, format_date, xlsxwriter
from odoo.tools.safe_eval import expr_eval, safe_eval
from odoo.models import check_method_name

class AccountReport(models.AbstractModel):
    _inherit = 'account.report'

    def _get_options(self, previous_options=None):
        self.ensure_one()
        # Create default options.
        options = {'unfolded_lines': (previous_options or {}).get('unfolded_lines', [])}

        for initializer in self._get_options_initializers_in_sequence():
            initializer(options, previous_options=previous_options)

        # Sort the buttons list by sequence, for rendering
        options['buttons'] = sorted(options['buttons'], key=lambda x: x.get('sequence', 90))

        currency_id_company_name = 'Bs'
        currency_id_dif_name = 'USD'
        if self._context.get('allowed_company_ids'):
            company_id = self._context.get('allowed_company_ids')[0]
            company = self.env['res.company'].browse(company_id)
            if company:
                currency_id_company_name = company.currency_id.symbol
                currency_id_dif_name = company.currency_id_dif.symbol
        currency_dif = currency_id_company_name
        if previous_options:
            if "currency_dif" in previous_options:
                currency_dif = previous_options['currency_dif']
        options['currency_dif'] = currency_dif
        options['currency_id_company_name'] = currency_id_company_name
        options['currency_id_dif_name'] = currency_id_dif_name
        slip_ids = None
        employee_ids = None
        rule_employee_integral_ids = None
        rule_employee_retenido_ids = None
        rule_company_aporte_ids = None
        structure_ids = None
        #variables de nómina
        if previous_options:
            if "rule_employee_integral_ids" in previous_options:
                rule_employee_integral_ids = previous_options['rule_employee_integral_ids']
            if "rule_employee_retenido_ids" in previous_options:
                rule_employee_retenido_ids = previous_options['rule_employee_retenido_ids']
            if "employee_ids" in previous_options:
                 employee_ids = previous_options['employee_ids']
            if 'rule_company_aporte_ids' in previous_options:
                rule_company_aporte_ids = previous_options['rule_company_aporte_ids']
            if 'structure_ids' in previous_options:
                structure_ids = previous_options['structure_ids']
            if 'slip_ids' in previous_options:
                slip_ids = previous_options['slip_ids']
        new_context = {
            **self._context,
            'currency_dif': currency_dif,
            'currency_id_company_name': currency_id_company_name,
            'rule_employee_integral_ids': rule_employee_integral_ids,
            'rule_employee_retenido_ids': rule_employee_retenido_ids,
            'employee_ids': employee_ids,
            'rule_company_aporte_ids': rule_company_aporte_ids,
            'structure_ids': structure_ids,
        }
        self.env.context = new_context
        return options

    def export_to_pdf(self, options):
        self.ensure_one()
        if not config['test_enable']:
            self = self.with_context(commit_assetsbundle=True)

        base_url = self.env['ir.config_parameter'].sudo().get_param('report.url') or self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        rcontext = {
            'mode': 'print',
            'base_url': base_url,
            'company': self.env.company,
        }
        new_context = {
            **self._context,
            'currency_dif': options['currency_dif'],
            'currency_id_company_name': options['currency_id_company_name'],
        }
        self.env.context = new_context
        print_mode_self = self.with_context(print_mode=True)

        body_html = print_mode_self.get_html(options, print_mode_self._get_lines(options))
        body = self.env['ir.ui.view']._render_template(
            "account_reports.print_template",
            values=dict(rcontext, body_html=body_html),
        )
        footer = self.env['ir.actions.report']._render_template("web.internal_layout", values=rcontext)
        footer = self.env['ir.actions.report']._render_template("web.minimal_layout", values=dict(rcontext, subst=True, body=markupsafe.Markup(footer.decode())))

        landscape = False
        if len(options['columns']) * len(options['column_groups']) > 5:
            landscape = True

        file_content = self.env['ir.actions.report']._run_wkhtmltopdf(
            [body],
            footer=footer.decode(),
            landscape=landscape,
            specific_paperformat_args={
                'data-report-margin-top': 10,
                'data-report-header-spacing': 10
            }
        )

        return {
            'file_name': self.get_default_report_filename('pdf'),
            'file_content': file_content,
            'file_type': 'pdf',
        }

    def _compute_search_template(self):
        self.search_template = 'l10n_ve_payroll_usd.search_template_generic_currency_dif'

    @api.model
    def format_value(self, value, currency=False, blank_if_zero=True, figure_type=None, digits=1):
        """ Formats a value for display in a report (not especially numerical). figure_type provides the type of formatting we want.
        """
        if figure_type == 'none':
            return value

        if value is None:
            return ''

        if figure_type == 'monetary':
            currency = currency or self.env.company.currency_id
            if self._context.get('currency_dif'):
                if self._context.get('currency_dif') == self._context.get('currency_id_company_name'):
                    currency = self.env.company.currency_id
                else:
                    currency = self.env.company.currency_id_dif
            digits = None
        elif figure_type == 'integer':
            currency = None
            digits = 0
        elif figure_type in ('date', 'datetime'):
            return format_date(self.env, value)
        else:
            currency = None

        if self.is_zero(value, currency=currency, figure_type=figure_type, digits=digits):
            if blank_if_zero:
                return ''
            # don't print -0.0 in reports
            value = abs(value)

        if self._context.get('no_format'):
            return value

        formatted_amount = formatLang(self.env, value, currency_obj=currency, digits=digits)

        if figure_type == 'percentage':
            return f"{formatted_amount}%"

        return formatted_amount
