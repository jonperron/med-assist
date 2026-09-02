"""Guard-clause coverage for scripts/build_model_image.sh.

The script has four phases: validate MODEL_DIR, validate the required files,
reject anything not on the required/optional allowlist, then stage a build
context and call `docker build` / `docker image inspect`. The first three are
exercised here with real subprocess runs and no daemon, no network, and no
real weights - each of them `exit 1` before the script ever touches `docker`,
including the allowlist check: it runs before `mktemp -d` stages anything.

The staging layout (files land flat at `models/<name>`, never nested) is also
covered, without a real build, by swapping in a `docker` stub that captures
the build context it was handed and then refuses - `set -euo pipefail` stops
the script at that `docker build` line, before `docker image inspect`,
`docker tag`, or anything that would need a real image. This machine has a
working Docker daemon on PATH, so every test here either exits before the
first `docker` invocation or replaces `docker` outright; none rely on the
real one behaving a particular way.

The actual build and its size assertion are not covered by an automated
test. That is verified by hand by running `scripts/build_model_image.sh`
locally and reading its own size-assertion output - see the script's header
comment.
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


def write_tripwire_docker_stub(fake_bin_dir: Path, marker: Path) -> None:
    """Install a `docker` that records being called and fails.

    The guard tests are meant to exit before the script ever runs `docker`.
    Relying on that leaves the isolation as a property of the code under test
    rather than of the harness: if a guard regressed below the build line,
    the test written to catch it would instead invoke the real daemon on this
    machine and run a build over placeholder files. This turns the argument
    into an assertion - the marker file is the evidence, and a real `docker`
    is never reachable because this one shadows it.
    """
    docker_stub = fake_bin_dir / "docker"
    docker_stub.write_text(
        "#!/usr/bin/env bash\n"
        'printf "%s\\n" "$*" >> "${DOCKER_TRIPWIRE}"\n'
        "exit 1\n"
    )
    docker_stub.chmod(0o755)
    marker.write_text("")


def run_script(model_dir: Path, tmp_path: Path) -> subprocess.CompletedProcess[str]:
    """Run the script with a `docker` that would record any invocation.

    Callers assert on the returned process; `assert_docker_was_never_called`
    checks the tripwire.
    """
    fake_bin_dir = tmp_path / "fake-bin"
    fake_bin_dir.mkdir(exist_ok=True)
    marker = tmp_path / "docker-tripwire"
    write_tripwire_docker_stub(fake_bin_dir, marker)
    return subprocess.run(
        ["bash", str(SCRIPT), "local"],
        env={
            "PATH": f"{fake_bin_dir}:{NARROW_PATH}",
            "MODEL_DIR": str(model_dir),
            "DOCKER_TRIPWIRE": str(marker),
        },
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )


def assert_docker_was_never_called(tmp_path: Path) -> None:
    marker = tmp_path / "docker-tripwire"
    assert marker.read_text() == "", (
        "the script reached docker; this guard is supposed to refuse before "
        f"any build begins. Invocations recorded: {marker.read_text()!r}"
    )


def write_refusing_docker_stub(fake_bin_dir: Path, capture_dir: Path) -> None:
    """Install a `docker` on PATH that captures the build context, then fails.

    Used only to observe the staging phase. `docker build` copies the context
    it was given into `capture_dir` and exits 1, so `set -euo pipefail` stops
    the script right there, before `docker image inspect`, `docker tag`, or
    any subcommand that would need a real image or a real daemon. Placed
    ahead of the system `docker` on PATH, so the real one on this machine is
    never invoked, and there is nothing left afterwards for a real `docker
    build` to have acted on even if the guard had not fired.
    """
    docker_stub = fake_bin_dir / "docker"
    docker_stub.write_text(
        "#!/usr/bin/env bash\n"
        'if [[ "$1" == "build" ]]; then\n'
        '  context="${@: -1}"\n'
        '  cp -r "${context}" "${CAPTURE_DIR}/staged-context"\n'
        "fi\n"
        "exit 1\n"
    )
    docker_stub.chmod(0o755)


def run_script_with_refusing_docker(
    model_dir: Path, tmp_path: Path, fake_bin_dir: Path, capture_dir: Path
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(SCRIPT), "local"],
        env={
            "PATH": f"{fake_bin_dir}:{NARROW_PATH}",
            "MODEL_DIR": str(model_dir),
            "CAPTURE_DIR": str(capture_dir),
        },
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )


def test_a_missing_model_directory_is_refused_before_any_docker_call(tmp_path):
    missing_dir = tmp_path / "does-not-exist"

    result = run_script(missing_dir, tmp_path)
    assert_docker_was_never_called(tmp_path)

    assert result.returncode == 1
    assert "no such directory" in result.stderr
    assert str(missing_dir) in result.stderr


def test_a_directory_missing_every_required_file_is_refused(tmp_path):
    model_dir = tmp_path / "empty-model"
    model_dir.mkdir()

    result = run_script(model_dir, tmp_path)
    assert_docker_was_never_called(tmp_path)

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
    assert_docker_was_never_called(tmp_path)

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
    assert_docker_was_never_called(tmp_path)

    assert result.returncode == 1
    assert f"missing: {name}" in result.stderr


def test_an_entry_not_on_either_allowlist_is_named_and_refused_before_staging(
    tmp_path: Path,
) -> None:
    # A stand-in for a training run's output directory: the required files
    # are present, but so is a checkpoint directory and a prediction dump -
    # and a prediction dump over this corpus is clinical text.
    model_dir = tmp_path / "training-run-output"
    model_dir.mkdir()
    for name in REQUIRED_FILES:
        (model_dir / name).write_text("placeholder, not a real model file")
    (model_dir / "checkpoint-500").mkdir()
    (model_dir / "predictions.json").write_text("placeholder, not real predictions")

    result = run_script(model_dir, tmp_path)
    assert_docker_was_never_called(tmp_path)

    assert result.returncode == 1
    assert "holds entries this script does not recognise" in result.stderr
    assert "checkpoint-500" in result.stderr
    assert "predictions.json" in result.stderr
    # The required files themselves are not reported as unrecognised.
    unexpected_block = result.stderr.split("does not recognise:")[1].split(
        "This image gets published"
    )[0]
    for name in REQUIRED_FILES:
        assert name not in unexpected_block
    # The guard fires before staging: the script never reaches the
    # "building ..." announcement, which only prints once a temp context
    # exists, and it never invokes docker - the real daemon on this
    # machine's PATH is not exercised.
    assert "building" not in result.stdout


def test_a_single_unrecognised_file_alongside_only_optional_files_is_still_named(
    tmp_path: Path,
) -> None:
    model_dir = tmp_path / "model-plus-one-stray-file"
    model_dir.mkdir()
    for name in REQUIRED_FILES:
        (model_dir / name).write_text("placeholder, not a real model file")
    (model_dir / "metrics.json").write_text('{"f1": 0.0}')
    (model_dir / "eval_predictions.json").write_text("not on either allowlist")

    result = run_script(model_dir, tmp_path)
    assert_docker_was_never_called(tmp_path)

    assert result.returncode == 1
    assert "holds entries this script does not recognise" in result.stderr
    assert "eval_predictions.json" in result.stderr
    # metrics.json is on the optional allowlist and must not be flagged.
    assert (
        "metrics.json"
        not in result.stderr.split("does not recognise:")[1].split(
            "This image gets published"
        )[0]
    )


def test_optional_files_are_accepted_and_staged_flat_under_models(
    tmp_path: Path,
) -> None:
    # The model directory's own name is deliberately not "models", so a
    # regression to a whole-directory `cp -r` would nest it visibly as
    # models/<this name>/config.json instead of models/config.json.
    model_dir = tmp_path / "some-training-run"
    model_dir.mkdir()
    for name in REQUIRED_FILES:
        (model_dir / name).write_text("placeholder, not a real model file")
    (model_dir / "metrics.json").write_text('{"f1": 0.0}')

    fake_bin_dir = tmp_path / "fake-bin"
    fake_bin_dir.mkdir()
    capture_dir = tmp_path / "capture"
    capture_dir.mkdir()
    write_refusing_docker_stub(fake_bin_dir, capture_dir)

    result = run_script_with_refusing_docker(
        model_dir, tmp_path, fake_bin_dir, capture_dir
    )

    # The stub docker always fails the build; that failure is only the
    # vehicle used to observe the context it was handed, not what is under
    # test here.
    assert result.returncode == 1
    assert "holds entries this script does not recognise" not in result.stderr

    staged_context = capture_dir / "staged-context"
    staged_models = staged_context / "models"
    assert staged_models.is_dir()

    staged_names = {path.name for path in staged_models.iterdir()}
    assert staged_names == set(REQUIRED_FILES) | {"metrics.json"}
    for name in staged_names:
        assert (staged_models / name).is_file()

    # Flat: never models/<model_dir name>/config.json, which is what a
    # cross-filesystem `cp -r` fallback used to produce.
    assert not (staged_models / model_dir.name).exists()

    # The Dockerfile.model context travels with the staged weights.
    assert (staged_context / "Dockerfile.model").is_file()
    assert (staged_context / "Dockerfile.model.dockerignore").is_file()
