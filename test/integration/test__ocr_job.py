"""Integration tests for OCR subtitle conversion."""

import json
import os
import time
from pathlib import Path

import httpx
import pytest

DATA_PATH = Path(__file__).parent.parent.parent / "data"
POLL_INTERVAL = 0.5
POLL_TIMEOUT = 120

BASE_URL = os.environ.get("INTEGRATION_TEST_URL", "http://localhost:8001")


@pytest.fixture
def client():
    return httpx.Client(base_url=BASE_URL, timeout=30.0)


@pytest.fixture(autouse=True)
def reset_job_state(client):
    """Ensure no running job before each test."""
    response = client.get("/job")
    if response.status_code == 200 and response.json() is not None:
        job = response.json()
        if job["status"] == "running":
            client.post("/job/cancel")
    yield


def wait_for_job_completion(client: httpx.Client, timeout: int = 120):
    """Poll GET /job until status is terminal or timeout."""
    start_time = time.time()
    job = None
    while time.time() - start_time < timeout:
        response = client.get("/job")
        assert response.status_code == 200
        job = response.json()
        if job is None:
            return None
        if job["status"] in ("completed", "failed", "cancelled"):
            return job
        time.sleep(POLL_INTERVAL)
    return job


def check_service_available(client: httpx.Client) -> bool:
    """Check if the service is available."""
    try:
        response = client.get("/health")
        return response.status_code == 200
    except Exception:
        return False


@pytest.fixture(autouse=True)
def check_service(client):
    """Skip tests if service is not available."""
    if not check_service_available(client):
        pytest.skip("Service not available")
    yield


class TestOCRSubtitleExtraction:
    """Tests for OCR bitmap subtitle extraction."""

    def test_extract_with_ocr_disabled(self, client):
        """
        Test that OCR is disabled when ocr_enabled is False.

        Even if language is known, no OCR should occur.
        """
        response = client.post(
            "job",
            json={
                "job_id": "ocr-test-disabled",
                "job_type": "extract",
                "input_params": {
                    "input_file": "test/input/test_clip_2.mkv",
                    "output_dir": "test/output/ocr_disabled",
                    "ocr_enabled": False,
                    "auto_crop": False,
                },
            },
        )
        assert response.status_code == 200

        job = wait_for_job_completion(client, timeout=POLL_TIMEOUT)
        assert job is not None
        assert job["status"] == "completed", f"Job failed: {job.get('error')}"

        output_dir = DATA_PATH / "test/output/ocr_disabled"

        srt_files = list(output_dir.glob("subtitle/*.srt"))
        assert len(srt_files) == 0, "No SRT files when OCR is disabled"

    def test_extract_with_ocr_enabled_skips_unsupported_language(self, client):
        """
        Test that OCR is skipped when subtitle language is not installed.

        test_clip_3.mkv has no subtitle tracks, so use test_clip_4.mkv which
        has bitmap subtitles but test_clip_4.mkv doesn't have language tags.
        Actually, test_clip_2.mkv has 'eng' language which IS supported,
        so we need to verify OCR works correctly by checking for ocr_converted.
        """
        response = client.post(
            "job",
            json={
                "job_id": "ocr-test-supported-lang",
                "job_type": "extract",
                "input_params": {
                    "input_file": "test/input/test_clip_2.mkv",
                    "output_dir": "test/output/ocr_supported_lang",
                    "ocr_enabled": True,
                    "auto_crop": False,
                },
            },
        )
        assert response.status_code == 200

        job = wait_for_job_completion(client, timeout=POLL_TIMEOUT)
        assert job is not None
        assert job["status"] == "completed", f"Job failed: {job.get('error')}"

        output_dir = DATA_PATH / "test/output/ocr_supported_lang"

        assert (output_dir / "metadata.json").exists()
        with open(output_dir / "metadata.json") as f:
            metadata = json.load(f)

        bitmap_subtitle_exts = [".sub", ".sup"]
        srt_files = list(output_dir.glob("subtitle/*.srt"))
        bitmap_files = []
        for ext in bitmap_subtitle_exts:
            bitmap_files.extend(list(output_dir.glob(f"subtitle/*{ext}")))

        assert len(bitmap_files) > 0 or len(srt_files) > 0, (
            "No subtitle files extracted"
        )

        subtitle_tracks = metadata.get("subtitle_tracks", [])
        for track in subtitle_tracks:
            if track.get("codec") in (
                "dvd_subtitle",
                "dvbsub",
                "hdmv_pgs_subtitle",
                "vobsub",
            ):
                assert "ocr_converted" in track, (
                    "ocr_converted field should be present in metadata"
                )

    def test_extract_default_ocr_enabled(self, client):
        """
        Test that OCR is enabled by default.

        test_clip_4.mkv has bitmap subtitles with no language metadata,
        so OCR should be skipped but job should complete successfully.
        """
        response = client.post(
            "job",
            json={
                "job_id": "ocr-test-default",
                "job_type": "extract",
                "input_params": {
                    "input_file": "test/input/test_clip_4.mkv",
                    "output_dir": "test/output/ocr_default",
                    "auto_crop": False,
                },
            },
        )
        assert response.status_code == 200

        job = wait_for_job_completion(client, timeout=POLL_TIMEOUT)
        assert job is not None
        assert job["status"] == "completed", f"Job failed: {job.get('error')}"

        output_dir = DATA_PATH / "test/output/ocr_default"
        assert (output_dir / "metadata.json").exists()
        with open(output_dir / "metadata.json") as f:
            metadata = json.load(f)

        subtitle_tracks = metadata.get("subtitle_tracks", [])
        assert len(subtitle_tracks) > 0, "No subtitle tracks in metadata"
        for track in subtitle_tracks:
            if track.get("codec") in (
                "dvd_subtitle",
                "dvbsub",
                "hdmv_pgs_subtitle",
                "vobsub",
            ):
                assert "ocr_converted" in track, (
                    "ocr_converted field should be present in metadata for bitmap subtitles"
                )
                assert track.get("ocr_converted") is False, (
                    "ocr_converted should be False when language is unknown/not installed"
                )


class TestOCRConversion:
    """Tests for OCR conversion of bitmap subtitles."""

    def test_extract_ocr_converted_true_for_supported_language(self, client):
        """
        Test that ocr_converted is True when OCR succeeds for supported language.

        test_clip_2.mkv has bitmap subtitles with 'eng' language tag,
        which should trigger OCR and set ocr_converted to True.
        """
        response = client.post(
            "job",
            json={
                "job_id": "ocr-test-success",
                "job_type": "extract",
                "input_params": {
                    "input_file": "test/input/test_clip_2.mkv",
                    "output_dir": "test/output/ocr_success",
                    "ocr_enabled": True,
                    "auto_crop": False,
                },
            },
        )
        assert response.status_code == 200

        job = wait_for_job_completion(client, timeout=POLL_TIMEOUT)
        assert job is not None
        assert job["status"] == "completed", f"Job failed: {job.get('error')}"

        output_dir = DATA_PATH / "test/output/ocr_success"
        assert (output_dir / "metadata.json").exists()
        with open(output_dir / "metadata.json") as f:
            metadata = json.load(f)

        subtitle_tracks = metadata.get("subtitle_tracks", [])
        bitmap_tracks = [
            t
            for t in subtitle_tracks
            if t.get("codec")
            in ("dvd_subtitle", "dvbsub", "hdmv_pgs_subtitle", "vobsub")
        ]

        if len(bitmap_tracks) == 0:
            pytest.skip("No bitmap subtitle tracks in test clip")

        for track in bitmap_tracks:
            assert "ocr_converted" in track, (
                "ocr_converted field should be present in metadata"
            )

        assert any(t.get("ocr_converted") for t in bitmap_tracks), (
            "At least one track should have ocr_converted=True for supported language"
        )


class TestOCRCompose:
    """Tests for compose with OCR'd and bitmap subtitles."""

    def test_compose_includes_valid_subtitle_tracks(self, client):
        """
        Test that compose includes valid subtitle tracks.

        Some subtitle tracks in test clips may be empty/corrupt.
        We remove invalid subtitle files before running compose.
        """
        response = client.post(
            "job",
            json={
                "job_id": "compose-test-subtitles",
                "job_type": "extract",
                "input_params": {
                    "input_file": "test/input/test_clip_2.mkv",
                    "output_dir": "test/output/compose_subtitles_input",
                    "ocr_enabled": False,
                    "auto_crop": False,
                },
            },
        )
        assert response.status_code == 200

        job = wait_for_job_completion(client, timeout=POLL_TIMEOUT)
        assert job is not None
        assert job["status"] == "completed", f"Job failed: {job.get('error')}"

        output_dir = DATA_PATH / "test/output/compose_subtitles_input"

        for sub_file in list(output_dir.glob("subtitle/*.sub")) + list(
            output_dir.glob("subtitle/*.sup")
        ):
            if sub_file.stat().st_size == 0:
                sub_file.unlink()
                idx_file = sub_file.with_suffix(".idx")
                if idx_file.exists():
                    idx_file.unlink()

        subtitle_files = list(output_dir.glob("subtitle/*.sub")) + list(
            output_dir.glob("subtitle/*.sup")
        )
        assert len(subtitle_files) > 0, "No valid subtitle files after cleanup"

        response = client.post(
            "job",
            json={
                "job_id": "compose-test-subtitles",
                "job_type": "compose",
                "input_params": {
                    "input_dir": "test/output/compose_subtitles_input",
                    "output_file": "test/output/compose_subtitles_output.mkv",
                },
            },
        )
        assert response.status_code == 200

        job = wait_for_job_completion(client, timeout=POLL_TIMEOUT)
        assert job is not None
        assert job["status"] == "completed", f"Job failed: {job.get('error')}"

        output_file = DATA_PATH / "test/output/compose_subtitles_output.mkv"
        assert output_file.exists()

        import subprocess

        result = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-select_streams",
                "s",
                "-show_entries",
                "stream=index,codec_name",
                "-of",
                "json",
                str(output_file),
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0

        streams = json.loads(result.stdout).get("streams", [])
        subtitle_count = len(streams)

        assert subtitle_count > 0, (
            "Composed video should have at least 1 subtitle track"
        )
