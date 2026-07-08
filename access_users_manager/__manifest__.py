# -*- coding: utf-8 -*-
{
    "name": "Access User Access Manager",
    "summary": "Access Profile User Manager ...",
    "description": """ ... """,
    "version": "17.0.0.0",
    "depends": ["base", "auth_signup", "web", "base_setup"],
    "external_dependencies": {
        "python": ["openpyxl", "werkzeug", "lxml"],
    },
    "data": [
        # security primero
        "security/ir.model.access.csv",

        # data/crons (sin numbercall en los xml)
        "data/ir_cron.xml",
        "data/user_profiles_cron.xml",
        "data/password_expire_mail.xml",
        "data/ir_module_category.xml",

        # vistas base / modelos que crean actions ANTES de menús
        "views/res_users_view.xml",
        "views/user_profiles.xml",
        "views/res_groups.xml",

        # vistas que meten menús y referencian actions
        "views/user_management_view.xml",
        "views/menu.xml",
        "views/reset_password.xml",
        "views/general_settings_view.xml",
    ],
    "post_init_hook": "access_post_install_report_action_hook",
    "demo": [],
    "assets": {
        "web.assets_backend": [
            "access_users_manager/static/src/js/hide_action_buttons.js",
        ],
        "web.assets_frontend": [
            "access_users_manager/static/src/js/eye_slash.js",
        ],
    },
    "installable": True,
    "auto_install": False,
    "application": True,
    "price": 85,
    "license": "OPL-1",
    "currency": "EUR",
    "images": [
        "static/description/module_image.png",
    ],
}
