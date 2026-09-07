from pathlib import Path

from app.services.media_ingestion import build_object_key, describe_media


def test_audio_folder_is_a_high_confidence_artifact_association(tmp_path: Path) -> None:
    root = tmp_path / "恩施知识库"
    path = root / "唐宋文物语音" / "西瓜碑语音" / "西瓜碑一（1）.m4a"
    path.parent.mkdir(parents=True)
    path.write_bytes(b"audio")

    descriptor = describe_media(path, root)

    assert descriptor.media_type == "audio"
    assert descriptor.mime_type == "audio/mp4"
    assert descriptor.artifact_name == "西瓜碑"
    assert descriptor.association_confidence == "folder"


def test_standard_package_audio_uses_the_artifact_folder(tmp_path: Path) -> None:
    root = tmp_path / "文物语料与语音"
    path = root / "史前至隋" / "三峡第一碑" / "三峡第一碑 音频" / "三峡第一碑1.mp3"
    path.parent.mkdir(parents=True)
    path.write_bytes(b"audio")

    descriptor = describe_media(path, root)

    assert descriptor.artifact_name == "三峡第一碑"
    assert descriptor.artifact_hint == "三峡第一碑"
    assert descriptor.association_confidence == "folder"


def test_flat_generated_video_is_left_for_review(tmp_path: Path) -> None:
    root = tmp_path / "恩施知识库"
    path = root / "图生视频库" / "牌坊.mp4"
    path.parent.mkdir(parents=True)
    path.write_bytes(b"video")

    descriptor = describe_media(path, root)

    assert descriptor.media_type == "video"
    assert descriptor.artifact_name is None
    assert descriptor.artifact_hint == "牌坊"
    assert descriptor.association_confidence == "review"


def test_object_key_is_content_addressed() -> None:
    sha256 = "a" * 64

    assert build_object_key(media_type="image", sha256=sha256, suffix=".JPG") == (
        "media/image/aa/" + sha256 + ".jpg"
    )
