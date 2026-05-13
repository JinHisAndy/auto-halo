from datetime import datetime, timezone
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.schemas.task import TaskResponse


def test_task_response_supports_retry_metadata_and_rewritten_title():
    task = TaskResponse.model_validate(
        {
            "id": "task-1",
            "title": "Original",
            "urls": ["https://example.com"],
            "status": "failed",
            "progress": 80,
            "stage_detail": "failed in publish",
            "error_msg": "boom",
            "keep_citations": False,
            "publish_type": "immediate",
            "scheduled_at": None,
            "minio_original_path": None,
            "minio_rewritten_path": None,
            "original_content": "<p>orig</p>",
            "rewritten_content": "<p>rewritten</p>",
            "rewritten_title": "Rewritten title",
            "failed_stage": "publishing",
            "trigger_source": "ui",
            "halo_post_id": "post-slug",
            "model_provider": "openai",
            "model_name": "gpt-test",
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        }
    )

    assert task.failed_stage == "publishing"
    assert task.trigger_source == "ui"
    assert task.rewritten_title == "Rewritten title"
