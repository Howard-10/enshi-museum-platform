from app.services.seed_knowledge_service import get_knowledge_seed


def test_first_knowledge_seed_is_available() -> None:
    seed = get_knowledge_seed()
    assert seed.seed_name == "enshi-core-docx-v1"
    assert seed.total_files == 28
    assert seed.copied_files == 28
