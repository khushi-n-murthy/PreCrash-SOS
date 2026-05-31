/**
 * TelemetryInterfaceManager
 * Production-grade client architecture to manage real-time Socket.IO links
 * and interface state syncing for PreCrash SoS.
 * 
 * Compatibility: dashboard_frontend/static/js/socket_client.js
 */
class TelemetryInterfaceManager {
    /**
     * @param {string} connection_uri - Socket.IO server address
     * @param {string} target_role - Role classification for connection handshake
     * @param {string} region_scope - Scope identifier for target district/region
     */
    constructor(connection_uri, target_role, region_scope) {
        this.connectionUri = connection_uri || window.location.origin;
        this.targetRole = target_role || "dispatcher";
        this.regionScope = region_scope || "PAC-CENTRAL";
        
        console.log(`[TelemetryInterfaceManager] Initializing connection handshake...`);

        // Connect utilizing Socket.IO with explicit query parameters
        this.socket = io(this.connectionUri, {
            query: {
                role: this.targetRole,
                district_id: this.regionScope
            },
            reconnectionAttempts: 10,
            reconnectionDelay: 2000,
            timeout: 10000
        });

        // Initialize event life cycle bindings
        this.initializeEventBindings();
    }

    /**
     * Set up listeners for connection state events and custom telemetry streams.
     */
    initializeEventBindings() {
        // Socket.IO Native Connect Event
        this.socket.on('connect', () => {
            console.log(`[TelemetryInterfaceManager] Handshake completed successfully. SID: ${this.socket.id}`);
            this.updateConnectionStatus(true);
        });

        // Socket.IO Native Disconnect Event
        this.socket.on('disconnect', (reason) => {
            console.warn(`[TelemetryInterfaceManager] Connection disconnected. Reason: ${reason}`);
            this.updateConnectionStatus(false);
        });

        // Socket.IO Native Connection Error Event
        this.socket.on('connect_error', (error) => {
            console.error(`[TelemetryInterfaceManager] Ingress handshake error:`, error);
            this.updateConnectionStatus(false);
        });

        // Contract Event Signature: incident_sos_trigger
        this.socket.on('incident_sos_trigger', (payload) => {
            console.log(`[TelemetryInterfaceManager] Intercepted telemetry signal: incident_sos_trigger`, payload);
            this.handleIncidentSosTrigger(payload);
        });
    }

    /**
     * Updates the status badge element inside the DOM with dynamic styling.
     * @param {boolean} isConnected 
     */
    updateConnectionStatus(isConnected) {
        const badge = document.getElementById("mesh-status-badge");
        if (badge) {
            if (isConnected) {
                badge.classList.add("online");
                badge.innerHTML = `
                    <span class="status-dot mesh-pulse-dot"></span>
                    <span>MESH LINK: ONLINE</span>
                `;
            } else {
                badge.classList.remove("online");
                badge.innerHTML = `
                    <span class="status-dot mesh-pulse-dot"></span>
                    <span>MESH LINK: OFFLINE</span>
                `;
            }
        }
    }

    /**
     * Injects a clean, corporate alert warning card upon intercepting live telemetry events.
     * @param {Object} payload - Stream parameters
     */
    handleIncidentSosTrigger(payload) {
        const panel = document.getElementById('alert-dispatch-panel');
        if (!panel) {
            console.error(`[TelemetryInterfaceManager] Target dispatch panel container "#alert-dispatch-panel" not found.`);
            return;
        }

        // Resiliently parse payload items
        const incidentId = payload.incident_id || payload.event_id || `INC-${Math.floor(1000 + Math.random() * 9000)}`;
        const message = payload.message || "Anomalous pre-crash telemetry detected on primary route.";
        const districtId = payload.district_id || payload.region_scope || this.regionScope;
        const responseRoute = payload.response_route || payload.routing_text || "Calculating rapid dispatch vector...";
        const severity = (payload.severity || "critical").toLowerCase();
        const probability = payload.probability !== undefined ? payload.probability : "0.94";
        const timestamp = payload.timestamp || new Date().toISOString().slice(11, 19);

        // Styling bindings
        const borderLeftColor = severity === "warning" ? "var(--accent-amber)" : "var(--accent-red)";
        const labelClass = severity === "warning" ? "severity-warning" : "severity-critical";

        // Inject structured HTML template matching portal design tokens
        panel.innerHTML = `
            <div class="injected-dispatch-card ${labelClass}" style="border-left: 3px solid ${borderLeftColor};">
                <div class="injected-card-header">
                    <span class="injected-badge">${severity.toUpperCase()} DISPATCH</span>
                    <span class="injected-time">${timestamp} UTC</span>
                </div>
                
                <h4 class="injected-title" style="margin-bottom: 6px;">ID: ${incidentId}</h4>
                
                <p class="injected-desc">
                    ${message}
                </p>
                
                <div class="injected-meta-grid">
                    <div class="injected-meta-row">
                        <span class="injected-meta-label">TARGET DISTRICT:</span>
                        <strong class="injected-meta-val font-mono">${districtId}</strong>
                    </div>
                    <div class="injected-meta-row">
                        <span class="injected-meta-label">RESPONSE ROUTING:</span>
                        <strong class="injected-meta-val" style="color: var(--accent-cyan); text-transform: uppercase;">${responseRoute}</strong>
                    </div>
                </div>

                <div class="injected-footer">
                    <div class="injected-probability">
                        PROBABILITY: <span>${probability}</span>
                    </div>
                </div>
            </div>
        `;

        // Sync panel header alert counters
        const alertCounter = document.getElementById('active-alert-counter');
        if (alertCounter) {
            alertCounter.textContent = "1 ACTIVE ALERT";
            alertCounter.style.color = borderLeftColor;
        }
    }
}

// Self-Instantiation upon DOMContentLoaded
document.addEventListener('DOMContentLoaded', () => {
    if (!window.telemetryManager) {
        const hostUrl = window.location.origin;
        const targetRole = "dispatcher";
        const regionScope = "PAC-CENTRAL";
        
        window.telemetryManager = new TelemetryInterfaceManager(hostUrl, targetRole, regionScope);
    }
});
