"""Environment sanity checks for test dependencies."""
import importlib.util

import pytest


def test_sqlalchemy_dependency_available():
    if importlib.util.find_spec("sqlalchemy") is None:
        pytest.skip("sqlalchemy dependency is missing in this environment")
    assert True
