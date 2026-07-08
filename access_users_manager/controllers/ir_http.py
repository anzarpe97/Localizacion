# -*- coding: utf-8 -*-

from odoo import models
from odoo.http import request
from datetime import datetime


class IrHttp(models.AbstractModel):
    _inherit = "ir.http"

    @classmethod
    def _authenticate(cls, endpoint):
        res = super(IrHttp, cls)._authenticate(endpoint=endpoint)
        # Only track activity if user is authenticated
        # Use sudo() to bypass permission checks during authentication
        if request.session.uid:
            activity = (
                request.env["recent.activity"]
                .sudo()
                .search([("access_session_id", "=", request.session.sid)])
            )
            if not activity:
                request.env["recent.activity"].sudo().create(
                    {
                        "access_user_id": request.session.uid,
                        "access_login_date": datetime.now(),
                        "access_duration": "Logged in",
                        "access_status": "active",
                        "access_session_id": request.session.sid,
                    }
                )
            if (
                request.env["recent.activity"]
                .sudo()
                .search(
                    [
                        ("access_session_id", "=", request.session.sid),
                        ("access_status", "=", "close"),
                    ]
                )
            ):
                request.session.logout(keep_db=True)
        return res
