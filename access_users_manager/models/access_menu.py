# -*- coding: utf-8 -*-

from odoo import api, fields, models
from odoo.http import request


class IrUiMenu(models.Model):
    _inherit = "ir.ui.menu"

    @api.model
    def search(self, args, offset=0, limit=None, order=None):
        """Hide menu which is selected inside User management only for the selected users"""
        # Preserve pagination/limits from callers (e.g., load_menus internals).
        menu_ids = super(IrUiMenu, self).search(
            args, offset=offset, limit=limit, order=order
        )
        current_user = self.env.user
        company_ids = False
        try:
            httprequest = getattr(request, "httprequest", None)
            if httprequest:
                company_ids = httprequest.cookies.get("cids") or False
        except RuntimeError:
            company_ids = False
        if company_ids:
            lst = [int(x) for x in company_ids.split(",") if x]
            access_hide_menu_ids = (
                self.env["user.management"]
                .sudo()
                .search(
                    [
                        ("access_user_ids", "in", current_user.ids),
                        ("active", "=", True),
                        ("access_company_ids", "in", lst),
                    ]
                )
                .mapped("access_hide_menu_ids")
            )
        else:
            access_hide_menu_ids = (
                self.env["user.management"]
                .search(
                    [("access_user_ids", "in", current_user.ids), ("active", "=", True)]
                )
                .mapped("access_hide_menu_ids")
            )
        menu_ids = menu_ids - access_hide_menu_ids
        return menu_ids
