from odoo import models, api
import logging

_logger = logging.getLogger(__name__)

# Referencias a métodos originales
original_create = models.BaseModel.create
original_write = models.BaseModel.write
original_unlink = models.BaseModel.unlink

def _serialize(vals):
    """ Convierte valores a string seguro para JSON """
    return str(vals)

def audited_write(self, vals):
    # BLINDAJE: Si audit.rule no existe (desinstalación), saltamos la lógica
    try:
        # Simplificación de la lógica: Solo procedemos si el modelo existe en el registro
        # Y la auditoría no está deshabilitada por contexto.
        if 'audit.rule' in self.env.registry and not self.env.context.get('disable_audit'):
            
            # Buscar la regla de auditoría para el modelo actual
            rule = self.env['audit.rule'].sudo().search([
                ('model_id.model', '=', self._name), 
                ('active', '=', True)
            ], limit=1)
            
            if rule:
                for record in self:
                    # Intentar obtener los valores anteriores de manera segura
                    old_vals = {}
                    for k in vals.keys():
                        try:
                            # Sólo registramos si el campo existe en el registro
                            if k in record:
                                # Usamos read() para obtener el valor del campo
                                old_vals[k] = record._read([k])[0][k]
                            # Nota: La auditoría en Odoo 18 suele usar el dict de vals, aquí reforzamos
                        except Exception:
                            # Ignorar campos que fallan la lectura (ej. campos de computación)
                            old_vals[k] = 'Error Reading Old Value'
                    
                    self.env['audit.log'].sudo().create({
                        'name': f"Modificación en {self._description or self._name}",
                        'model_id': rule.model_id.id,
                        'res_id': record.id,
                        'operation_type': 'write',
                        'old_values': _serialize(old_vals),
                        'new_values': _serialize(vals),
                        'user_id': self.env.uid
                    })
    except Exception as e:
        # Registramos la excepción en el servidor para ver si hay un problema de ACL/modelo
        _logger.exception(f"Error durante auditoría WRITE en modelo {self._name}: {e}")
        pass # Permitimos que la operación original continúe

    return original_write(self, vals)

def audited_create(self, vals):
    record = original_create(self, vals)
    try:
        # Lógica simplificada
        if 'audit.rule' in self.env.registry and not self.env.context.get('disable_audit'):
            rule = self.env['audit.rule'].sudo().search([('model_id.model', '=', self._name), ('active', '=', True)], limit=1)
            if rule:
                self.env['audit.log'].sudo().create({
                    'name': f"Creación de {self._description or self._name}",
                    'model_id': rule.model_id.id,
                    'res_id': record.id,
                    'operation_type': 'create',
                    'new_values': _serialize(vals),
                    'user_id': self.env.uid
                })
    except Exception as e:
        _logger.exception(f"Error durante auditoría CREATE en modelo {self._name}: {e}")
        pass
    return record

def audited_unlink(self):
    # Lógica de unlink ya era limpia, solo ajustamos el manejo de errores
    try:
        if 'audit.rule' in self.env.registry and not self.env.context.get('disable_audit'):
            rule = self.env['audit.rule'].sudo().search([('model_id.model', '=', self._name), ('active', '=', True)], limit=1)
            if rule:
                for record in self:
                    self.env['audit.log'].sudo().create({
                        'name': f"Eliminación de {self._description or self._name}",
                        'model_id': rule.model_id.id,
                        'res_id': record.id,
                        'operation_type': 'unlink',
                        'old_values': f"ID: {record.id}, Name: {record.display_name}",
                        'user_id': self.env.uid
                    })
    except Exception as e:
        _logger.exception(f"Error durante auditoría UNLINK en modelo {self._name}: {e}")
        pass
    return original_unlink(self)

# Aplicar el parche
models.BaseModel.write = audited_write
models.BaseModel.create = audited_create
models.BaseModel.unlink = audited_unlink