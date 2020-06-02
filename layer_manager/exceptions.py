class ModelAlreadyRegistered(Exception):
    """The model you are trying to create is already registered"""


class TableAlreadyExists(Exception):
    """The table you are trying to create already exists in the database"""


class InvalidGeometryType(Exception):
    def __init__(self, geometry_type: str):
        f"""Invalid geometry type: \"{geometry_type}\"."""


class NoFeaturesProvided(Exception):
    def __init__(self, results):
        f"""No features provided in results: \"{results}\"."""
