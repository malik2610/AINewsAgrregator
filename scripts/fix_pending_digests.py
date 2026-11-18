import sys
from pathlib import Path
from datetime import datetime, timezone

# Add project root to Python path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.database.repository import Repository
from app.database.models import Digest


digest_ids = [
    "youtube:r0cJOa9MZsE",
    "openai:https://openai.com/index/openai-to-acquire-pierre",
    "openai:https://openai.com/index/a-thousand-fewer-paths-to-root",
]

repo = Repository()

try:
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    updated = (
        repo.session.query(Digest)
        .filter(
            Digest.id.in_(digest_ids),
            Digest.sent_at.is_(None)
        )
        .update(
            {Digest.created_at: now},
            synchronize_session=False
        )
    )

    repo.session.commit()

    print(f"Updated {updated} pending digests.")

finally:
    repo.session.close()