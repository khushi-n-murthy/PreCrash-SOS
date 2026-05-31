"""
gap_analyzer.py  —  PreCrash SoS  |  Member A: Data & ML Engine
Responder Gap Index calculation engine.

Computes a spatial coverage score that measures how "exposed" a hazard zone is,
given the current distribution of active responders.

Gap Index  →  0.0  : fully covered (many nearby responders)
             1.0  : completely uncovered (no responders in scan radius)
"""

import numpy as np
from core_config.global_constants import (
    EARTH_RADIUS_EQUATORIAL_KM,
    SPATIAL_SCAN_RADIUS_KM,
    RISK_THRESHOLD_HIGH,
)


class TargetGapScorer:
    """
    Evaluates coverage gaps at incident coordinates using haversine geometry
    and inverse-distance weighting of nearby responders.
    """

    # Weight decay: each responder within radius reduces gap by this factor
    PROXIMITY_DECAY_WEIGHT = 0.15

    @staticmethod
    def compute_haversine_distance(lat1: float, lon1: float,
                                   lat2: float, lon2: float) -> float:
        """
        Returns the great-circle distance in kilometres between two
        WGS-84 coordinate pairs using the haversine formula.

        Parameters
        ----------
        lat1, lon1 : float  — origin point (decimal degrees)
        lat2, lon2 : float  — destination point (decimal degrees)

        Returns
        -------
        float  — distance in kilometres
        """
        phi1, phi2 = np.radians(lat1), np.radians(lat2)
        dphi = np.radians(lat2 - lat1)
        dlam = np.radians(lon2 - lon1)

        a = (np.sin(dphi / 2.0) ** 2
             + np.cos(phi1) * np.cos(phi2) * np.sin(dlam / 2.0) ** 2)

        return EARTH_RADIUS_EQUATORIAL_KM * 2.0 * np.arctan2(
            np.sqrt(a), np.sqrt(1.0 - a)
        )

    def evaluate_responder_gap_index(
        self,
        hazard_lat: float,
        hazard_lon: float,
        target_risk_score: float,
        active_responders: list[dict],
    ) -> float:
        """
        Computes the Responder Gap Index for a hazard location.

        The index blends the raw ML risk score with an inverse-distance
        coverage factor: the denser the nearby responder cluster, the lower
        the returned gap value.

        Parameters
        ----------
        hazard_lat      : float  — incident latitude
        hazard_lon      : float  — incident longitude
        target_risk_score : float — ML-predicted risk in [0.0, 1.0]
        active_responders : list[dict]
            Each dict must contain keys:
              'lat'  (float)  — responder current latitude
              'lon'  (float)  — responder current longitude
            Optional:
              'unit_type' (str) — e.g. "AMBULANCE", "POLICE", "FIRE"

        Returns
        -------
        float — gap index clamped to [0.0, 1.0]
                Higher value → more exposed / fewer nearby responders.
        """
        proximity_weight_sum = 0.0

        for responder in active_responders:
            dist = self.compute_haversine_distance(
                hazard_lat, hazard_lon,
                responder["lat"], responder["lon"],
            )
            if dist <= SPATIAL_SCAN_RADIUS_KM:
                # Inverse-distance weight: closer responders contribute more
                proximity_weight_sum += 1.0 / (dist + 1.0)

        raw_gap = target_risk_score - (
            proximity_weight_sum * self.PROXIMITY_DECAY_WEIGHT
        )
        return float(np.clip(raw_gap, 0.0, 1.0))

    def is_critical(self, gap_index: float) -> bool:
        """Returns True when gap index exceeds the configured high-risk threshold."""
        return gap_index >= RISK_THRESHOLD_HIGH

    def rank_hazard_zones(
        self,
        hazard_zones: list[dict],
        active_responders: list[dict],
    ) -> list[dict]:
        """
        Batch-scores a list of hazard zones and returns them sorted by
        descending gap index (most exposed first).

        Parameters
        ----------
        hazard_zones : list[dict]
            Each dict must contain:
              'zone_id'    (str)
              'lat'        (float)
              'lon'        (float)
              'risk_score' (float)

        active_responders : list[dict]  — see evaluate_responder_gap_index

        Returns
        -------
        list[dict]  — original dicts augmented with 'gap_index' and 'critical'
                      keys, sorted descending by gap_index.
        """
        scored = []
        for zone in hazard_zones:
            gap = self.evaluate_responder_gap_index(
                zone["lat"], zone["lon"],
                zone["risk_score"],
                active_responders,
            )
            scored.append({
                **zone,
                "gap_index": gap,
                "critical": self.is_critical(gap),
            })

        scored.sort(key=lambda z: z["gap_index"], reverse=True)
        return scored