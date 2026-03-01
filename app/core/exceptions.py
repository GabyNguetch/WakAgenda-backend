"""
app/core/exceptions.py
Exceptions métier centralisées.
Principe SOLID : Open/Closed – on étend sans modifier le code existant.
"""

from fastapi import HTTPException, status


class CredentialsException(HTTPException):
    def __init__(self, detail: str = "Identifiants invalides."):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
            headers={"WWW-Authenticate": "Bearer"},
        )


class NotFoundException(HTTPException):
    def __init__(self, resource: str = "Ressource"):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"{resource} introuvable.",
        )


class AlreadyExistsException(HTTPException):
    def __init__(self, resource: str = "Ressource"):
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"{resource} existe déjà.",
        )


class ForbiddenException(HTTPException):
    def __init__(self, detail: str = "Accès refusé."):
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=detail,
        )
