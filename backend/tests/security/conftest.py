import pytest

def pytest_collection_modifyitems(items):
    """
    Applique automatiquement le marqueur @pytest.mark.security
    à tous les tests situés sous le répertoire tests/security/.
    """
    for item in items:
        if "security" in str(item.fspath):
            item.add_marker(pytest.mark.security)
