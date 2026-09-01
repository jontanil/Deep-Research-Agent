from src.config.paths import project_root, resolve_from_project_root


def test_project_root_is_repo_root():
    assert (project_root() / "pyproject.toml").exists()
    assert (project_root() / "src").is_dir()


def test_resolve_relative_anchors_to_project_root():
    assert resolve_from_project_root("Result.md") == project_root() / "Result.md"


def test_resolve_absolute_returned_unchanged(tmp_path):
    assert resolve_from_project_root(tmp_path / "out.md") == tmp_path / "out.md"


def test_resolve_is_cwd_independent(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert resolve_from_project_root("Result.md") == project_root() / "Result.md"