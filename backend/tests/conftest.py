"""Aísla los tests de los secretos y del modo de publicación local.

Cada test parte de un entorno sin autenticación; los tests de seguridad
habilitan la protección explícitamente con monkeypatch.setenv().
Esto NO cambia el .env real ni desprotege la aplicación ejecutada.
"""
import pytest


@pytest.fixture(autouse=True)
def isolated_demo_environment(monkeypatch):
    monkeypatch.setenv('AUTH_ENABLED', 'false')
    monkeypatch.setenv('PUBLIC_DEMO', 'false')
    monkeypatch.setenv('DEMO_ACCESS_CODE', '')
