from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from threading import Barrier

import pytest


def test_root_redirects_to_activity_page(client):
    # Arrange
    url = "/"

    # Act
    response = client.get(url, follow_redirects=False)

    # Assert
    assert response.status_code == 307
    assert response.headers["location"] == "/static/index.html"


def test_get_activities_returns_rosters(client, activity_data):
    # Arrange
    expected = deepcopy(activity_data)

    # Act
    response = client.get("/activities")

    # Assert
    assert response.status_code == 200
    assert response.json() == expected
    assert activity_data == expected


def test_signup_adds_one_participant(client, activity_data):
    # Arrange
    email = "student+chess@mergington.edu"
    expected = deepcopy(activity_data)
    expected["Chess Club"]["participants"].append(email)

    # Act
    response = client.post("/activities/Chess Club/signup", params={"email": email})

    # Assert
    assert response.status_code == 200
    assert response.json() == {"message": f"Signed up {email} for Chess Club"}
    assert activity_data == expected


def test_duplicate_signup_does_not_change_rosters(client, activity_data):
    # Arrange
    email = activity_data["Chess Club"]["participants"][0]
    expected = deepcopy(activity_data)

    # Act
    response = client.post("/activities/Chess Club/signup", params={"email": email})

    # Assert
    assert response.status_code == 400
    assert response.json() == {"detail": "Student already signed up for this activity"}
    assert activity_data == expected


def test_signup_to_full_activity_does_not_change_rosters(client, activity_data):
    # Arrange
    activity_data["Chess Club"]["participants"].append("second@mergington.edu")
    expected = deepcopy(activity_data)

    # Act
    response = client.post(
        "/activities/Chess Club/signup", params={"email": "third@mergington.edu"}
    )

    # Assert
    assert response.status_code == 400
    assert response.json() == {"detail": "Activity is full"}
    assert activity_data == expected


def test_concurrent_signup_does_not_exceed_activity_capacity(client, activity_data):
    email = "student@mergington.edu"
    start = Barrier(2)

    def signup():
        start.wait()
        return client.post("/activities/Chess Club/signup", params={"email": email})

    with ThreadPoolExecutor(max_workers=2) as executor:
        responses = list(executor.map(lambda _: signup(), range(2)))

    assert sorted(response.status_code for response in responses) == [200, 400]
    assert activity_data["Chess Club"]["participants"].count(email) == 1


@pytest.mark.parametrize("method, action", [("POST", "signup"), ("DELETE", "unregister")])
def test_unknown_activity_does_not_change_rosters(client, activity_data, method, action):
    # Arrange
    expected = deepcopy(activity_data)
    url = f"/activities/Unknown Club/{action}"

    # Act
    response = client.request(method, url, params={"email": "student@mergington.edu"})

    # Assert
    assert response.status_code == 404
    assert response.json() == {"detail": "Activity not found"}
    assert activity_data == expected


def test_unregister_removes_only_requested_participant(client, activity_data):
    # Arrange
    email = activity_data["Chess Club"]["participants"][0]
    activity_data["Chess Club"]["participants"].append("second@mergington.edu")
    activity_data["Art Club"]["participants"].append(email)
    expected = deepcopy(activity_data)
    expected["Chess Club"]["participants"].remove(email)

    # Act
    response = client.delete("/activities/Chess Club/unregister", params={"email": email})

    # Assert
    assert response.status_code == 200
    assert response.json() == {"message": f"Unregistered {email} from Chess Club"}
    assert activity_data == expected


def test_unregister_missing_participant_does_not_change_rosters(client, activity_data):
    # Arrange
    expected = deepcopy(activity_data)

    # Act
    response = client.delete(
        "/activities/Chess Club/unregister", params={"email": "absent@mergington.edu"}
    )

    # Assert
    assert response.status_code == 400
    assert response.json() == {"detail": "Student is not signed up for this activity"}
    assert activity_data == expected


@pytest.mark.parametrize("method, action", [("POST", "signup"), ("DELETE", "unregister")])
def test_missing_email_does_not_change_rosters(client, activity_data, method, action):
    # Arrange
    expected = deepcopy(activity_data)
    url = f"/activities/Chess Club/{action}"

    # Act
    response = client.request(method, url)

    # Assert
    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["query", "email"]
    assert activity_data == expected


def test_participant_can_sign_up_after_unregistering(client, activity_data):
    # Arrange
    email = activity_data["Chess Club"]["participants"][0]
    expected = deepcopy(activity_data)
    removal = client.delete("/activities/Chess Club/unregister", params={"email": email})
    assert removal.status_code == 200
    assert email not in activity_data["Chess Club"]["participants"]

    # Act
    response = client.post("/activities/Chess Club/signup", params={"email": email})

    # Assert
    assert response.status_code == 200
    assert response.json() == {"message": f"Signed up {email} for Chess Club"}
    assert activity_data == expected