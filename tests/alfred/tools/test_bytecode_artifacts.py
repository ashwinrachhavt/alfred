from __future__ import annotations

from scripts.bytecode_artifacts import iter_bytecode_artifacts, remove_bytecode_artifacts


def test_iter_bytecode_artifacts_skips_local_dependency_caches(tmp_path):
    source_cache = tmp_path / "apps" / "alfred" / "__pycache__"
    source_cache.mkdir(parents=True)
    source_cache.joinpath("main.cpython-311.pyc").write_bytes(b"bytecode")
    tmp_path.joinpath("orphan.pyc").write_bytes(b"bytecode")

    venv_cache = tmp_path / ".venv" / "lib" / "__pycache__"
    venv_cache.mkdir(parents=True)
    venv_cache.joinpath("dependency.pyc").write_bytes(b"bytecode")

    node_modules = tmp_path / "web" / "node_modules"
    node_modules.mkdir(parents=True)
    node_modules.joinpath("generated.pyc").write_bytes(b"bytecode")

    artifacts = {path.relative_to(tmp_path) for path in iter_bytecode_artifacts(tmp_path)}

    assert artifacts == {
        source_cache.relative_to(tmp_path),
        tmp_path.joinpath("orphan.pyc").relative_to(tmp_path),
    }


def test_remove_bytecode_artifacts_removes_only_project_artifacts(tmp_path):
    source_cache = tmp_path / "apps" / "alfred" / "__pycache__"
    source_cache.mkdir(parents=True)
    source_cache.joinpath("main.cpython-311.pyc").write_bytes(b"bytecode")

    venv_cache = tmp_path / ".venv" / "lib" / "__pycache__"
    venv_cache.mkdir(parents=True)
    dependency_artifact = venv_cache / "dependency.pyc"
    dependency_artifact.write_bytes(b"bytecode")

    removed = {path.relative_to(tmp_path) for path in remove_bytecode_artifacts(tmp_path)}

    assert removed == {source_cache.relative_to(tmp_path)}
    assert not source_cache.exists()
    assert dependency_artifact.exists()
