from odoo import http
from odoo.http import request
from odoo.addons.web.controllers.session import Session

class AuditController(http.Controller):
    
    @http.route('/audit/log_connection_event', type='json', auth='user')
    def log_connection_event(self, offline_time, online_time, user_id):
        """ Recibe el evento desde Javascript """
        request.env['audit.log'].sudo().create({
            'name': 'Pérdida de Conexión a Internet',
            'operation_type': 'connection_lost',
            'user_id': user_id,
            'old_values': f"Conexión perdida: {offline_time}",
            'new_values': f"Conexión recuperada: {online_time}",
        })
        return {'status': 'success'}

class AuditSession(Session):
    @http.route('/web/session/authenticate', type='json', auth="none")
    def authenticate(self, db, login, password, base_location=None):
        try:
            return super(AuditSession, self).authenticate(db, login, password, base_location)
        except Exception:
            # Capturar fallo de autenticación (cuando user/pass son incorrectos Odoo lanza AccessDenied)
            # Nota: Esto captura errores genéricos, para Auth pura a veces se requiere heredar addons/auth_signup
            # Sin embargo, monitorear request.session.uid después del super también sirve.
            pass
        
        # Si llegamos aquí y no hay UID, falló
        if not request.session.uid and db:
             # Usamos un cursor nuevo para escribir porque la transacción actual puede fallar
            with request.env.registry.cursor() as new_cr:
                env = request.env(cr=new_cr)
                env['audit.log'].sudo().create({
                    'name': f"Intento de acceso fallido: {login}",
                    'operation_type': 'access_error',
                    'new_values': f"IP: {request.httprequest.remote_addr}",
                    'model_id': False
                })
        return super(AuditSession, self).authenticate(db, login, password, base_location)