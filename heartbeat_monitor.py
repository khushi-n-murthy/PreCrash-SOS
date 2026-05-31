import time
import threading

TIMEOUT = 300
class DynamicFailsafeEngine:
    def __init__(self, datastore):
        self.db = datastore
        self.is_running = True

        self.monitor_thread = threading.Thread(
            target=self.monitor_loop,
            daemon=True
        )
    def start(self):
        self.monitor_thread.start()
    def monitor_loop(self):
        while self.is_running:
            current_time = time.time()
            responders = self.db.get_all_active_responders()
            for responder in responders:
                last_ping = responder["timestamp_last_ping"]
                if current_time - last_ping > TIMEOUT:
                    self.db.update_responder_status(
                        responder["responder_user_id"],
                        "OFFLINE"
                    )
                    print(f"{responder['responder_user_id']} OFFLINE")
            time.sleep(15)