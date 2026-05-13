from datetime import datetime, timezone
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.schemas.task import TaskResponse


def test_task_response_supports_generated_tags():
    task = TaskResponse.model_validate(
        {
            "id": "task-1",
            "title": "Original",
            "urls": ["https://example.com"],
            "status": "completed",
            "progress": 100,
            "stage_detail": "done",
            "error_msg": None,
            "keep_citations": False,
            "publish_type": "immediate",
            "scheduled_at": None,
            "minio_original_path": None,
            "minio_rewritten_path": None,
            "original_content": "<p>orig</p>",
            "rewritten_content": "<p>rewritten</p>",
            "rewritten_title": "New Title",
            "generated_tags": [{"name": "Linux", "color": "blue"}],
            "failed_stage": None,
            "trigger_source": "ui",
            "halo_post_id": "slug-1",
            "model_provider": "openai",
            "model_name": "gpt-test",
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        }
    )

    assert task.generated_tags == [{"name": "Linux", "color": "blue"}]
