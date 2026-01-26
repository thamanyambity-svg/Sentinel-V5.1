# Rôles autorisés à exécuter des commandes sensibles
ADMIN_ROLES = {"ADMIN", "OWNER"}

def is_admin(user_roles):
    """
    user_roles: iterable de rôles (str)
    """
    return any(role in ADMIN_ROLES for role in user_roles)
