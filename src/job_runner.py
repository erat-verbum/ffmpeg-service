import asyncio
import os
from pathlib import Path
from typing import Any, Callable, Optional


class JobRunner:
    """Manages job execution with progress updates and cancellation support."""

    def __init__(
        self, job_ref: Optional[dict[str, Any]], get_status: Callable[[], str]
    ):
        self._job_ref = job_ref
        self._get_status = get_status

    async def run(self) -> dict[str, Any]:
        """
        Extract all frames from a video file to PNG images.

        Returns:
            dict: Result containing extraction status and frame count

        Raises:
            ValueError: If input file doesn't exist
            RuntimeError: If ffmpeg fails
        """
        input_params = self._job_ref.get("input_params", {}) if self._job_ref else {}
        input_file = input_params.get("input_file")
        output_dir = input_params.get("output_dir")

        if not input_file or not output_dir:
            raise ValueError("input_file and output_dir are required")

        input_path = Path(input_file)
        if not input_path.exists():
            raise ValueError(f"Input file not found: {input_file}")

        os.makedirs(output_dir, exist_ok=True)

        output_pattern = os.path.join(output_dir, "frame_%04d.png")

        process = await asyncio.create_subprocess_exec(
            "ffmpeg",
            "-i",
            str(input_path),
            "-y",
            output_pattern,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        self._update_progress(10)

        try:
            await process.wait()
        except asyncio.CancelledError:
            process.kill()
            await process.wait()
            raise

        if process.returncode != 0:
            if process.stderr is not None:
                stderr = await process.stderr.read()
                error_msg = stderr.decode() if stderr else "Unknown error"
            else:
                error_msg = "Unknown error"
            raise RuntimeError(f"FFmpeg failed: {error_msg}")

        frame_files = list(Path(output_dir).glob("frame_*.png"))
        frame_count = len(frame_files)

        return {
            "completed": True,
            "input_file": input_file,
            "output_dir": output_dir,
            "frame_count": frame_count,
        }

    def _update_progress(self, progress: int) -> None:
        """Update job progress."""
        if self._job_ref:
            self._job_ref["progress"] = progress


async def run_job(
    job_ref: Optional[dict[str, Any]],
    get_status: Callable[[], str],
) -> dict[str, Any]:
    """Entry point for running a job."""
    runner = JobRunner(job_ref, get_status)
    return await runner.run()
