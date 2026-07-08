# -*- coding: utf-8 -*-

import logging
from odoo.exceptions import UserError

from odoo.addons.auth_signup.controllers.main import AuthSignupHome
import odoo
import odoo.modules.registry
from odoo import http
from odoo.tools.translate import _
from odoo.addons.web.controllers.utils import (
    ensure_db,
    _get_login_redirect_url,
    is_user_internal,
)
from odoo.addons.web.controllers.home import Home
from datetime import datetime
from odoo.addons.web.controllers.session import Session
from odoo.http import request
from dateutil.relativedelta import relativedelta
import json, werkzeug

_logger = logging.getLogger(__name__)

SIGN_UP_REQUEST_PARAMS = {
    "db",
    "login",
    "debug",
    "token",
    "message",
    "error",
    "scope",
    "mode",
    "redirect",
    "redirect_hostname",
    "email",
    "name",
    "partner_id",
    "password",
    "confirm_password",
    "city",
    "country_id",
    "lang",
    "signup_email",
}
LOGIN_SUCCESSFUL_PARAMS = set()


class accessSessionWebsite(Session):

    @http.route(
        "/web/session/logout",
        type="http",
        auth="none",
        website=True,
        multilang=False,
        sitemap=False,
    )
    def logout(self, redirect="/web"):
        # Use sudo() to bypass permission checks during logout
        activity = (
            request.env["recent.activity"]
            .sudo()
            .search([("access_session_id", "=", request.session.sid)])
        )
        if activity:
            activity.access_action_logout()
        return super().logout(redirect=redirect)


class Home(Home):
    @http.route(['/odoo', '/odoo/<path:subpath>'], type='http', auth="none")
    def odoo_redirect(self, subpath=None, **kw):
        ensure_db()
        user_id = request.env.user.browse(request.session.uid)
        
        # Corrección: Aseguramos que el usuario exista en la sesión antes de revisar si la contraseña expiró
        if user_id and user_id.access_is_passwd_expired:
            request.session.logout()
            
        company_id = request.httprequest.cookies.get('cids') if request.httprequest.cookies.get('cids') else False
        if kw.get('debug') and kw.get('debug') != "0":
            if company_id:
                lst = [int(x) for x in request.httprequest.cookies.get('cids').split(',')]
                profile_management = request.env['user.management'].sudo().search(
                    [('active', '=', True), ('access_disable_debug_mode', '=', True), ('access_company_ids', 'in', lst),
                     ('access_user_ids', 'in', user_id.id)], limit=1)
            else:
                profile_management = request.env['user.management'].sudo().search(
                    [('active', '=', True), ('access_disable_debug_mode', '=', True), ('access_user_ids', 'in', user_id.id)], limit=1)
            if profile_management:
                return request.redirect('/web?debug=0')
        
        return self.web_client(**kw)

    @http.route("/web/login")
    def web_login(self, *args, **kw):
        redirect = None
        ensure_db()
        request.params["login_success"] = False
        if request.httprequest.method == "GET" and redirect and request.session.uid:
            return request.redirect(redirect)
        if not request.uid:
            request.update_env(user=odoo.SUPERUSER_ID)

        values = {
            k: v for k, v in request.params.items() if k in SIGN_UP_REQUEST_PARAMS
        }
        try:
            values["databases"] = http.db_list()
        except odoo.exceptions.AccessDenied:
            values["databases"] = None

        if request.httprequest.method == "POST":
            try:
                # Corrección: Agregado limit=1 para evitar ValueError: Expected singleton
                user = (
                    request.env["res.users"]
                    .sudo()
                    .search([("login", "=", request.params["login"])], limit=1)
                )
                login = True
                # Check that is password is expired then show password expire message while login.
                if (
                    user
                    and not user.has_group("base.group_system")
                    and user.access_is_passwd_expired
                ):
                    values["error"] = _("Password Expired")
                    login = False
                
                if login:
                    # Corrección: Sintaxis de autenticación para Odoo 17 (pasando login y password directo)
                    uid = request.session.authenticate(
                        request.session.db, 
                        request.params["login"], 
                        request.params["password"]
                    )

                    request.params["login_success"] = True
                    return request.redirect(
                        self._login_redirect(uid, redirect=redirect)
                    )
            except odoo.exceptions.AccessDenied as e:
                if e.args == odoo.exceptions.AccessDenied().args:
                    values["error"] = _("Wrong login/password")
                else:
                    values["error"] = e.args[0]
        else:
            if "error" in request.params and request.params.get("error") == "access":
                values["error"] = _(
                    "Only employees can access this database. Please contact the administrator."
                )

        if "login" not in values and request.session.get("auth_login"):
            values["login"] = request.session.get("auth_login")

        if not odoo.tools.config["list_db"]:
            values["disable_database_manager"] = True

        response = request.render("web.login", values)
        response.headers["X-Frame-Options"] = "SAMEORIGIN"
        response.headers["Content-Security-Policy"] = "frame-ancestors 'self'"

        # Check that Auth module is installed or not.
        # If installed then it will update the providers on the login page.
        module = (
            request.env["ir.module.module"]
            .sudo()
            .search([("name", "=", "auth_oauth"), ("state", "=", "installed")], limit=1)
        )
        if module:
            response.qcontext.update(self.get_auth_signup_config())
            if request.session.uid:
                if request.httprequest.method == "GET" and request.params.get(
                    "redirect"
                ):
                    # Redirect if already logged in and redirect param is present
                    return request.redirect(request.params.get("redirect"))
                # Add message for non-internal user account without redirect if account was just created
                if response.location == "/web/login_successful" and kw.get(
                    "confirm_password"
                ):
                    return request.redirect_query(
                        "/web/login_successful", query={"account_created": True}
                    )
            if (
                request.httprequest.method == "GET"
                and request.session.uid
                and request.params.get("redirect")
            ):
                # Redirect if already logged in and redirect param is present
                return request.redirect(request.params.get("redirect"))
            providers = self.list_providers()
            if response.is_qweb:
                error = request.params.get("oauth_error")
                if error == "1":
                    error = _("Sign up is not allowed on this database.")
                elif error == "2":
                    error = _("Access Denied")
                elif error == "3":
                    error = _(
                        "You do not have access to this database or your invitation has expired. Please ask for an invitation and be sure to follow the link in your invitation email."
                    )
                else:
                    error = None

                response.qcontext["providers"] = providers
                if error:
                    response.qcontext["error"] = error

            return response
        else:
            response.qcontext.update(self.get_auth_signup_config())
            if request.session.uid:
                if request.httprequest.method == "GET" and request.params.get(
                    "redirect"
                ):
                    # Redirect if already logged in and redirect param is present
                    return request.redirect(request.params.get("redirect"))
                # Add message for non-internal user account without redirect if account was just created
                if response.location == "/web/login_successful" and kw.get(
                    "confirm_password"
                ):
                    return request.redirect_query(
                        "/web/login_successful", query={"account_created": True}
                    )
            return response

    def list_providers(self):
        try:
            providers = (
                request.env["auth.oauth.provider"]
                .sudo()
                .search_read([("enabled", "=", True)])
            )
        except Exception:
            providers = []
        for provider in providers:
            return_url = request.httprequest.url_root + "auth_oauth/signin"
            state = self.get_state(provider)
            params = dict(
                response_type="token",
                client_id=provider["client_id"],
                redirect_uri=return_url,
                scope=provider["scope"],
                state=json.dumps(state),
                # nonce=base64.urlsafe_b64encode(os.urandom(16)),
            )
            provider["auth_link"] = "%s?%s" % (
                provider["auth_endpoint"],
                werkzeug.urls.url_encode(params),
            )
        return providers


class accessAuthSignupHomeInherit(AuthSignupHome):

    @http.route(
        "/web/reset_password/direct",
        type="http",
        auth="public",
        website=True,
        sitemap=False,
        csrf=False,
    )
    def access_auth_reset_password(self, *args, **kw):
        qcontext = self.get_auth_signup_qcontext()
        response = request.render(
            "access_users_manager.reset_password_direct", qcontext
        )
        return response

    @http.route(
        "/web/reset_password/submit",
        type="http",
        methods=["POST"],
        auth="public",
        website=True,
        csrf=False,
    )
    def access_change_password(self, *args, **kw):
        values = {}
        if kw["confirm_new_password"] == kw["new_password"]:
            try:
                uid = False
                
                # Corrección: Sintaxis de autenticación para Odoo 17
                uid = request.session.authenticate(
                    request.session.db,
                    kw["user_name"], 
                    kw["old_password"]
                )
                
                user = request.env["res.users"].sudo().search([("id", "=", uid)])
                vals = {
                    "access_password_update": datetime.now(),
                    "password": kw["confirm_new_password"],
                    "access_is_passwd_expired": False,
                }
                expiry_month = (
                    request.env["ir.config_parameter"]
                    .sudo()
                    .get_param("access_users_manager.password_expire_in_days")
                )
                if expiry_month:
                    expire_date = user.access_password_update + relativedelta(
                        days=int(expiry_month)
                    )
                    vals["access_password_expire_date"] = expire_date
                user.sudo().write(vals)
                return request.redirect("/web/login")

            except:
                values["error"] = _("Login or Password Is Incorrect")
                return request.render(
                    "access_users_manager.reset_password_direct", values
                )
        else:
            values["error"] = _("Password Not Match")
            return request.render("access_users_manager.reset_password_direct", values)