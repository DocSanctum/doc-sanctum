import os
import tempfile

import pytest

from backend.app.services.tree_builder import build_local_tree
from backend.app.models.source import Source


def _make_source(path: str) -> Source:
    return Source(
        id="test-id",
        name="test",
        type="local",
        path=path,
        polling_interval_seconds=None,
        created_at=None,
        status="active",
        error_message=None,
    )


def test_build_local_tree_tilde_path():
    """~/... 경로가 expanduser 없이 실패하던 버그 재현 및 수정 확인."""
    with tempfile.TemporaryDirectory() as tmpdir:
        md_file = os.path.join(tmpdir, "doc.md")
        with open(md_file, "w") as f:
            f.write("# Hello")

        # HOME을 tmpdir 부모로 설정해 ~/dirname 형식으로 테스트
        dirname = os.path.basename(tmpdir)
        parent = os.path.dirname(tmpdir)
        tilde_path = f"~/{dirname}"

        original_home = os.environ.get("HOME")
        try:
            os.environ["HOME"] = parent
            source = _make_source(tilde_path)
            result = build_local_tree(source)
            paths = [c["path"] for c in result["root"]["children"]]
            assert "doc.md" in paths
        finally:
            if original_home is not None:
                os.environ["HOME"] = original_home


def test_build_local_tree_absolute_path():
    """절대 경로는 expanduser 전후 동일하게 동작해야 한다."""
    with tempfile.TemporaryDirectory() as tmpdir:
        md_file = os.path.join(tmpdir, "readme.md")
        with open(md_file, "w") as f:
            f.write("# Readme")

        source = _make_source(tmpdir)
        result = build_local_tree(source)
        paths = [c["path"] for c in result["root"]["children"]]
        assert "readme.md" in paths


def test_build_local_tree_nonexistent_path_raises():
    """존재하지 않는 경로는 FileNotFoundError를 발생시켜야 한다."""
    source = _make_source("/nonexistent/path/that/does/not/exist")
    with pytest.raises(FileNotFoundError):
        build_local_tree(source)


def test_build_local_tree_only_md_files():
    """비 .md 파일은 트리에 포함되지 않아야 한다."""
    with tempfile.TemporaryDirectory() as tmpdir:
        for name in ["doc.md", "image.png", "notes.txt", "spec.md"]:
            with open(os.path.join(tmpdir, name), "w") as f:
                f.write("")

        source = _make_source(tmpdir)
        result = build_local_tree(source)
        paths = [c["path"] for c in result["root"]["children"]]
        assert "doc.md" in paths
        assert "spec.md" in paths
        assert "image.png" not in paths
        assert "notes.txt" not in paths
