class BreadcrumbLogger:

    def __init__(self):
        self.trails = {}

    def add_location(self, user_id, lat, lon):

        if user_id not in self.trails:
            self.trails[user_id] = []

        self.trails[user_id].append({
            "lat": lat,
            "lon": lon
        })

        # keep only latest 50 points
        self.trails[user_id] = self.trails[user_id][-50:]