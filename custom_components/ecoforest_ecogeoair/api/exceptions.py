
class EcoGeoAirError(Exception):
    pass


class EcoGeoAirConnectionError(EcoGeoAirError):
    pass


class EcoGeoAirAuthError(EcoGeoAirError):
    def __init__(self, status: int) -> None:
        self.status = status


class EcoGeoAirApiError(EcoGeoAirError):
    pass


class EcoGeoAirDeviceError(EcoGeoAirError):
    pass