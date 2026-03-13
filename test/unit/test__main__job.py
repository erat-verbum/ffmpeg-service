import asyncio

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch

from src.main import app, reset_job


@pytest.fixture(autouse=True)
def reset_state():
    """Reset job state before each test."""
    reset_job()
    yield
    reset_job()


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def mock_job():
    """Mock the job runner to avoid actual ffmpeg execution."""

    async def mock_run_job(job_ref, get_status):
        await asyncio.sleep(0.1)
        job_ref["progress"] = 100
        return {"completed": True, "job_type": "extract", "frame_count": 10}

    with patch("src.main.run_job", mock_run_job):
        yield


def test_health_check(client):
    """Test health check endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "timestamp" in data


def test_get_job_empty(client):
    """Test GET /job returns empty when no job exists."""
    response = client.get("/job")
    assert response.status_code == 200
    assert response.json() is None


def test_start_job_missing_job_type(client):
    """Test POST /job returns 422 when job_type missing."""
    response = client.post("/job", json={"job_id": "test-job-1"})
    assert response.status_code == 422


def test_start_job_missing_params_extract(client):
    """Test POST /job returns 400 when input_params missing for extract."""
    response = client.post(
        "/job",
        json={"job_id": "test-job-1", "job_type": "extract"},
    )
    assert response.status_code == 400
    assert "extract job requires input_file and output_dir" in response.json()["detail"]


def test_start_job_missing_input_file(client):
    """Test POST /job returns 400 when input_file missing for extract."""
    response = client.post(
        "/job",
        json={
            "job_id": "test-job-1",
            "job_type": "extract",
            "input_params": {"output_dir": "data/out"},
        },
    )
    assert response.status_code == 400


def test_start_job_missing_output_dir(client):
    """Test POST /job returns 400 when output_dir missing for extract."""
    response = client.post(
        "/job",
        json={
            "job_id": "test-job-1",
            "job_type": "extract",
            "input_params": {"input_file": "data/in.mp4"},
        },
    )
    assert response.status_code == 400


def test_start_job_rejects_when_running(client, mock_job):
    """Test POST /job returns 409 when job already running."""
    client.post(
        "/job",
        json={
            "job_id": "job-1",
            "job_type": "extract",
            "input_params": {"input_file": "data/in.mp4", "output_dir": "data/out"},
        },
    )

    response = client.post(
        "/job",
        json={
            "job_id": "job-2",
            "job_type": "extract",
            "input_params": {"input_file": "data/in.mp4", "output_dir": "data/out"},
        },
    )
    assert response.status_code == 409
    assert "already running" in response.json()["detail"]


def test_get_job_returns_current(client, mock_job):
    """Test GET /job returns current job."""
    client.post(
        "/job",
        json={
            "job_id": "my-job",
            "job_type": "extract",
            "input_params": {"input_file": "data/in.mp4", "output_dir": "data/out"},
        },
    )

    response = client.get("/job")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == "my-job"
    assert data["status"] == "running"
    assert data["job_type"] == "extract"


def test_cancel_job(client, mock_job):
    """Test POST /job/cancel cancels running job."""
    client.post(
        "/job",
        json={
            "job_id": "cancel-me",
            "job_type": "extract",
            "input_params": {"input_file": "data/in.mp4", "output_dir": "data/out"},
        },
    )

    response = client.post("/job/cancel")
    assert response.status_code == 200

    response = client.get("/job")
    assert response.json()["status"] == "cancelled"


def test_cancel_job_no_job(client):
    """Test POST /job/cancel returns 404 when no job."""
    response = client.post("/job/cancel")
    assert response.status_code == 404


def test_cancel_job_completed(client):
    """Test POST /job/cancel returns 400 when job completed."""

    async def quick_job(job_ref, get_status):
        job_ref["status"] = "completed"
        return {"done": True}

    with patch("src.main.run_job", quick_job):
        client.post(
            "/job",
            json={
                "job_id": "done-job",
                "job_type": "extract",
                "input_params": {"input_file": "data/in.mp4", "output_dir": "data/out"},
            },
        )

    response = client.get("/job")
    assert response.json()["status"] == "completed"

    response = client.post("/job/cancel")
    assert response.status_code == 400


def test_start_job_compose_missing_params(client):
    """Test POST /job returns 400 when input_params missing for compose."""
    response = client.post(
        "/job",
        json={"job_id": "test-job-1", "job_type": "compose"},
    )
    assert response.status_code == 400
    assert "compose job requires input_dir and output_file" in response.json()["detail"]


def test_start_job_compose_missing_input_dir(client):
    """Test POST /job returns 400 when input_dir missing for compose."""
    response = client.post(
        "/job",
        json={
            "job_id": "test-job-1",
            "job_type": "compose",
            "input_params": {"output_file": "data/out.mp4"},
        },
    )
    assert response.status_code == 400


def test_start_job_compose_missing_output_file(client):
    """Test POST /job returns 400 when output_file missing for compose."""
    response = client.post(
        "/job",
        json={
            "job_id": "test-job-1",
            "job_type": "compose",
            "input_params": {"input_dir": "data/frames"},
        },
    )
    assert response.status_code == 400
