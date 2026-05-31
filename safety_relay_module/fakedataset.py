class FakeDB:

    def __init__(self):
        self.responders = []

    def get_all_active_responders(self):
        return self.responders

    def update_responder_status(self, user_id, status):

        for r in self.responders:
            if r["responder_user_id"] == user_id:
                r["status"] = status