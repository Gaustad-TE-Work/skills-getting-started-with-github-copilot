import pytest
from fastapi.testclient import TestClient

import src.app as app_module


@pytest.fixture
def activity_data(monkeypatch):
    data = {
        "Chess Club": {
            "description": "Play chess",
            "schedule": "Fridays, 3:30 PM - 5:00 PM",
            "max_participants": 2,
            "participants": ["member@mergington.edu"],
        },
        "Art Club": {
            "description": "Make art",
            "schedule": "Mondays, 3:30 PM - 5:00 PM",
            "max_participants": 2,
            "participants": [],
        },
    }
    monkeypatch.setattr(app_module, "activities", data)
    return data


@pytest.fixture
def client(activity_data):
    with TestClient(app_module.app) as test_client:
        yield test_client