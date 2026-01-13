/** @odoo-module **/
import { registry } from "@web/core/registry";
import { browser } from "@web/core/browser/browser";
import { rpc } from "@web/core/network/rpc"; // En Odoo 18 a veces se usa env.services.rpc, pero import directo suele funcionar
import { session } from "@web/session";

const connectionMonitorService = {
    // Los servicios requieren declarar dependencias, aunque esté vacío
    dependencies: [],
    
    start(env) {
        // Lógica de inicio del servicio
        if (!session.user_id) return; // Solo monitorear si hay usuario logueado

        console.log(">>> Auditoría SENIAT: Monitor de conexión iniciado.");

        window.addEventListener('offline', () => {
            console.log(">>> Conexión Perdida (Offline)");
            const eventData = {
                type: 'connection_lost',
                timestamp: new Date().toISOString(),
                user_id: session.user_id
            };
            browser.localStorage.setItem('audit_offline_event', JSON.stringify(eventData));
        });

        window.addEventListener('online', async () => {
            console.log(">>> Conexión Recuperada (Online)");
            const offlineData = browser.localStorage.getItem('audit_offline_event');
            
            if (offlineData) {
                const data = JSON.parse(offlineData);
                try {
                    // Usamos la ruta del controlador que definimos en Python
                    await rpc('/audit/log_connection_event', {
                        'offline_time': data.timestamp,
                        'online_time': new Date().toISOString(),
                        'user_id': data.user_id
                    });
                    
                    // Limpiamos el storage para no duplicar
                    browser.localStorage.removeItem('audit_offline_event');
                    console.log(">>> Evento de desconexión enviado a auditoría.");
                    
                } catch (e) {
                    console.error("Error enviando log de auditoría SENIAT", e);
                }
            }
        });
    }
};

// CAMBIO CRÍTICO: Registramos en 'services', no en 'main_components'
registry.category("services").add("connectionMonitor", connectionMonitorService);