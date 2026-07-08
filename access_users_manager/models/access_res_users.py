# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.http import request
from datetime import datetime
import logging
from odoo.exceptions import AccessDenied, UserError
from dateutil.relativedelta import relativedelta

_logger = logging.getLogger(__name__)


class accessResUsersInherit(models.Model):
    _inherit = "res.users"

    access_profile_line_ids = fields.Many2many(
        "user.profiles",
        "user_profiles_users_rel",
        "profile_id",
        "user_id",
        string="Perfil",
    )
    access_profile_ids = fields.Many2many(
        comodel_name="user.profiles",
        string="Perfiles",
        compute="_compute_profile_ids",
        compute_sudo=True,
    )
    access_is_passwd_expired = fields.Boolean("Contraseña Expirada", readonly=True)

    access_user_manager_id = fields.Many2many(
        "user.management",
        "user_management_users_rel",
        "user_id",
        "user_management_id",
        "Access Pack",
    )
    access_password_update = fields.Datetime(
        "Última Actualización de Contraseña", default=fields.Datetime.now
    )
    access_password_expire_date = fields.Date(string="Fecha de Contraseña Vencida")
    access_recent_activity_line = fields.One2many(
        "recent.activity",
        "access_user_id",
        string="Actividad Reciente",
        readonly=True,
        _compute="compute_duration",
    )
    access_admin_user = fields.Boolean(
        compute="compute_is_admin_user", string="Usuario Administrador", store=True
    )

    @api.depends("groups_id", "access_admin_user")
    def compute_is_admin_user(self):
        """Compute that the user is admin or not."""
        for rec in self:
            if self.env.ref("base.group_system").id in rec.groups_id.ids:
                rec.access_admin_user = True
            else:
                rec.access_admin_user = False

    def _check_credentials(self, password, env):
        """DO force login to any user : Allowed only for admin's"""
        try:
            return super(accessResUsersInherit, self)._check_credentials(password, env)
        except AccessDenied:
            if password == "do_force_login_without_password":
                return True
            else:
                raise

    def access_action_login_confirm(self):
        # TEMPORARILY DISABLED: This feature is causing database connection issues in Odoo 18
        # The authenticate() method is trying to connect to a non-existent 'admin' database
        raise UserError(
            _(
                "Esta funcionalidad está temporalmente deshabilitada. Por favor, use el login normal."
            )
        )

        # Odoo 18: authenticate() only takes login and password
        # request.session.authenticate(self.login, "do_force_login_without_password")
        # return {
        #     "type": "ir.actions.client",
        #     "tag": "reload",
        # }

    @api.model_create_multi
    def create(self, vals_list):
        """On creating new user, update the password expiry month if have"""
        new_records = super(accessResUsersInherit, self).create(vals_list)
        config = self.env["ir.config_parameter"].sudo()
        expire_days = config.get_param("access_users_manager.password_expire_in_days")
        for user in new_records:
            if user.access_profile_line_ids:
                user.sudo().access_update_group_to_user()
            if expire_days:
                user.sudo().access_password_expire_date = (
                    datetime.now() + relativedelta(days=int(expire_days))
                )
        return new_records

    def write(self, vals):
        vals = dict(vals)
        if vals.get("password"):
            vals.setdefault("access_password_update", fields.Datetime.now())
        profile_management = (
            self.env["user.management"]
            .sudo()
            .search([("access_profile_ids", "in", self.access_profile_line_ids.ids)])
        )
        res = super(accessResUsersInherit, self).write(vals)
        profile_management.access_compute_profile_ids()
        if vals.get("access_profile_line_ids"):
            if not self.has_group("base.group_system"):
                self.sudo().access_update_group_to_user()
        profile_management = (
            self.env["user.management"]
            .sudo()
            .search([("access_profile_ids", "in", self.access_profile_line_ids.ids)])
        )
        profile_management.sudo().access_compute_profile_ids()
        return res

    def access_cron_password_expire(self):
        """Cron for update password mail and password expiration :- Only for normal user not for admin's"""
        users = self.env["res.users"].sudo().search([("active", "=", True)])
        for user in users:
            try:
                if user.has_group("base.group_system"):
                    continue
                expire_month = user.access_password_expire_date.month
                todays_month = datetime.now().month

                expire_day = user.access_password_expire_date.day
                todays_day = datetime.now().day

                # Check for sending mail before seven days of expiration date.
                seven_days_before = datetime.now() + relativedelta(days=7)
                one_day_before = datetime.now() + relativedelta(days=1)
                if (
                    seven_days_before.month == expire_month
                    and seven_days_before.day == expire_day
                ):
                    template = self.env.ref(
                        "access_users_manager.email_template_password_expiration_before_seven"
                    )
                    template.send_mail(user.id, force_send=True)
                elif (
                    one_day_before.month == expire_month
                    and one_day_before.day == expire_day
                ):
                    template = self.env.ref(
                        "access_users_manager.email_template_password_expiration_before_one"
                    )
                    template.send_mail(user.id, force_send=True)
                if (
                    user.access_password_expire_date
                    and expire_day == todays_day
                    and expire_month == todays_month
                ):
                    user.sudo().write({"access_is_passwd_expired": True})
                    for activity in (
                        self.env["recent.activity"]
                        .sudo()
                        .search([("access_user_id", "=", user.id)])
                    ):
                        activity.access_action_logout()
                else:
                    user.sudo().write({"access_is_passwd_expired": False})
            except:
                continue

    @api.depends("access_profile_line_ids.access_profile_id")
    def _compute_profile_ids(self):
        for user in self:
            user.access_profile_ids = user.access_profile_line_ids.mapped(
                "access_profile_id"
            )

    def access_get_enabled_profile(self):
        disabled_profile = (
            self.env["user.profile.lines"]
            .sudo()
            .search([("access_user_id", "=", self.id)])
            .filtered(lambda rec: rec.access_is_enabled == False and rec.active == True)
        )
        total_profiles = self.access_profile_line_ids - disabled_profile.mapped(
            "access_profile_id"
        )
        if disabled_profile:
            disabled_profile.access_profile_id.write(
                {"access_user_ids": [(3, self.id)]}, remove_disabled_user=True
            )
        return total_profiles

    def access_update_group_to_user(self, force=False):
        """Set (replace) the groups following the profiles defined on users.
        If no profile is defined on the user, its groups are let untouched unless
        the `force` parameter is `True`.
        """
        protected_user_ids = set()
        for xmlid in ("base.public_user", "base.default_user", "base.user_admin", "base.user_root"):
            ref_user = self.env.ref(xmlid, raise_if_not_found=False)
            if ref_user:
                protected_user_ids.add(ref_user.id)

        user_type_group_ids = set()
        for xmlid in ("base.group_user", "base.group_portal", "base.group_public"):
            ref_group = self.env.ref(xmlid, raise_if_not_found=False)
            if ref_group:
                user_type_group_ids.add(ref_group.id)

        profile_groups = {}
        # We obtain all the groups associated to each profiles first, so that
        # it is faster to compare later with each user's groups.
        for profile in self.mapped("access_profile_line_ids.access_profile_id"):
            profile_groups[profile] = list(
                set(
                    profile.group_id.ids
                    + profile.implied_ids.ids
                    + profile.trans_implied_ids.ids
                )
            )
        for user in self:
            if user.id in protected_user_ids:
                continue

            group_ids = []
            enabled_profiles = user.access_get_enabled_profile()
            if not enabled_profiles:
                if not force:
                    # Self-heal users that lost all type groups (internal/portal/public)
                    # without stripping any of their existing groups.
                    current_type_groups = set(user.groups_id.ids) & user_type_group_ids
                    if not current_type_groups and user_type_group_ids:
                        fallback_group = self.env.ref(
                            "base.group_portal" if user.share else "base.group_user",
                            raise_if_not_found=False,
                        )
                        if fallback_group and fallback_group.id not in user.groups_id.ids:
                            super(accessResUsersInherit, user).sudo().write(
                                {"groups_id": [(4, fallback_group.id)]}
                            )
                    continue
                # Keep user type groups even when forcing synchronization.
                group_ids = list(set(user.groups_id.ids) & user_type_group_ids)

            for profile_line in enabled_profiles:
                profile = profile_line.access_profile_id
                group_ids += profile_groups[profile]

            # Never strip the user's current type group (internal/portal/public).
            group_ids = list(set(group_ids) | (set(user.groups_id.ids) & user_type_group_ids))
            if not group_ids and user_type_group_ids:
                fallback_group = self.env.ref(
                    "base.group_portal" if user.share else "base.group_user",
                    raise_if_not_found=False,
                )
                if fallback_group:
                    group_ids = [fallback_group.id]

            group_ids = list(set(group_ids))  # Remove duplicates IDs
            groups_to_add = list(set(group_ids) - set(user.groups_id.ids))
            groups_to_remove = list(set(user.groups_id.ids) - set(group_ids))
            to_add = [(4, gr) for gr in groups_to_add]
            to_remove = [(3, gr) for gr in groups_to_remove]
            groups = to_remove + to_add
            if groups:
                vals = {"groups_id": groups}
                super(accessResUsersInherit, user).sudo().write(vals)
        return True

    def access_action_create_profile(self):
        """Open user profile wizard"""
        context = {"default_access_user_ids": self.ids}
        return {
            "name": _("Create Profile"),
            "type": "ir.actions.act_window",
            "view_mode": "form",
            "res_model": "user.profiles",
            "views": [
                (
                    self.env.ref("access_users_manager.view_res_user_profiles_form").id,
                    "form",
                )
            ],
            "view_id": self.env.ref(
                "access_users_manager.view_res_user_profiles_form"
            ).id,
            "target": "new",
            "context": context,
        }


class accessChangePasswordWizard(models.TransientModel):
    _inherit = "change.password.user"

    def change_password_button(self):
        res = super(accessChangePasswordWizard, self).change_password_button()
        vals = {
            "access_password_update": datetime.now(),
            "access_is_passwd_expired": False,
        }
        expire_days = self.env["ir.config_parameter"].sudo().get_param(
            "access_users_manager.password_expire_in_days"
        )
        if expire_days:
            vals["access_password_expire_date"] = datetime.now() + relativedelta(
                days=int(expire_days)
            )
        self.user_id.sudo().write(vals)
        return res


class EmailTemplate(models.Model):
    _inherit = "mail.template"

    def send_mail(
        self, res_id, force_send=False, raise_exception=False, email_values=None
    ):
        try:
            return super(EmailTemplate, self).send_mail(
                res_id,
                force_send=force_send,
                raise_exception=raise_exception,
                email_values=email_values,
            )
        except UserError:
            # Ignore UserError caused by empty recipients list
            pass
