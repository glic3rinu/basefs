class ValidationError(Exception):
    pass


class IntegrityError(Exception):
    pass


class PermissionDenied(Exception):
    pass


class Exists(Exception):
    pass


class DoesNotExist(Exception):
    pass
