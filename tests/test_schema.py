import json
from services.repository import PlaybookRepository


def test_playbook_json_is_valid():
    repo = PlaybookRepository()
    with open(repo.data_dir / "playbook.json", "r", encoding="utf-8") as f:
        data = json.load(f)
    pb = repo.load_playbook()
    assert pb.version == data["version"]
