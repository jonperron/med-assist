"""Guard-clause coverage for scripts/build_model_image.sh.

The script has three phases: validate MODEL_DIR, stage a build context, and
call `docker build` / `docker image inspect`. Only the first is exercised
here - a missing MODEL_DIR and a directory missing one of the files
`from_pretrained` reads. Both cases `exit 1` before the script ever touches
`docker`, so these run with no daemon, no network, and no real weights.

The staging and build phases are not covered by an automated test. They need
a working `docker` and, to observe the failure mode the script's own comment
worries about (an ignored `models/` producing a silently empty image), an
actual build. That is verified by hand by running
`scripts/build_model_image.sh` locally and reading its own size-assertion
output - see the script's header comment - rather than faked here with a
stub `docker` binary that would only prove the stub was called correctly.
"""

import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "build_model_image.sh"

REQUIRED_FILES = (
    "config.json",
    "model.safetensors",
    "tokenizer.json",
    "tokenizer_config.json",
)

# Deliberately not the fixtures under backend/tests/fixtures and not real
# weights: these are empty placeholder files, only their names matter to the
# check under test.
NARROW_PATH = "/usr/bin:/bin"


def run_script(model_dir, tmp_path):
    return subprocess.run(
        ["bash", str(SCRIPT), "local"],
        env={"PATH": NARROW_PATH, "MODEL_DIR": str(model_dir)},
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )


def test_a_missing_model_directory_is_refused_before_any_docker_call(tmp_path):
    missing_dir = tmp_path / "does-not-exist"

    result = run_script(missing_dir, tmp_path)

    assert result.returncode == 1
    assert "no such directory" in result.stderr
    assert str(missing_dir) in result.stderr


def test_a_directory_missing_every_required_file_is_refused(tmp_path):
    model_dir = tmp_path / "empty-model"
    model_dir.mkdir()

    result = run_script(model_dir, tmp_path)

    assert result.returncode == 1
    assert "is not a model directory; missing:" in result.stderr
    for name in REQUIRED_FILES:
        assert name in result.stderr


def test_a_directory_missing_one_required_file_names_only_that_one(tmp_path):
    model_dir = tmp_path / "partial-model"
    model_dir.mkdir()
    for name in REQUIRED_FILES:
        if name != "model.safetensors":
            (model_dir / name).write_text("placeholder, not a real model file")

    result = run_script(model_dir, tmp_path)

    assert result.returncode == 1
    assert "missing: model.safetensors" in result.stderr
    # The files that are present are not reported as missing.
    assert "config.json" not in result.stderr.split("missing:")[1]


@pytest.mark.parametrize("name", REQUIRED_FILES)
def test_a_directory_with_only_directories_named_like_the_files_still_fails(
    tmp_path, name
):
    # required_files uses `-f`, so a directory of that name must not pass as
    # the file transformers expects to read.
    model_dir = tmp_path / "dir-not-file"
    model_dir.mkdir()
    for required in REQUIRED_FILES:
        if required == name:
            (model_dir / required).mkdir()
        else:
            (model_dir / required).write_text("placeholder, not a real model file")

    result = run_script(model_dir, tmp_path)

    assert result.returncode == 1
    assert f"missing: {name}" in result.stderr
