"""Coupling checks between the files that ship the NER model as its own image.

Three files must move together: `backend/Dockerfile` copies the weights out
of the model image and points `NER_MODEL_NAME` at where it put them,
`backend/Dockerfile.model` is the other end of that `COPY --from` inside the
model image, and `docker-compose.dev.yml` is the only place a host directory
is allowed to shadow that same path for local retraining work -
`docker-compose.yml`, the default deployment shape, must not. A rename on
one side of any of these without the other is exactly the kind of drift that
produced the original bug this arrangement replaced: a container that starts,
answers 503 forever on `/readyz`, and says nothing about why. None of this
needs Docker, a daemon, or the real weights: it is plain text already
committed in the repository, read as text rather than parsed as YAML so this
file adds no dependency of its own - PyYAML is only ever pulled in
transitively here, by the model stack's own dependencies, not declared for
the backend project itself.
"""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_DOCKERFILE = REPO_ROOT / "backend" / "Dockerfile"
MODEL_DOCKERFILE = REPO_ROOT / "backend" / "Dockerfile.model"
COMPOSE_BASE = REPO_ROOT / "docker-compose.yml"
COMPOSE_DEV = REPO_ROOT / "docker-compose.dev.yml"

# The bind-mount syntax always writes the container path preceded by a colon
# (`source:/app/models` or `source:/app/models:ro`); prose about the same
# path, such as the comment in docker-compose.yml explaining why there is no
# mount, does not happen to produce this substring. Verified against both
# files as they stand.
MODEL_MOUNT_MARKER = ":/app/models"


def test_the_base_compose_file_does_not_bind_mount_over_the_model_path() -> None:
    compose_base = COMPOSE_BASE.read_text(encoding="utf-8")

    assert MODEL_MOUNT_MARKER not in compose_base, (
        "docker-compose.yml must not shadow the weights baked into the "
        "image - a bind mount here, including one Docker creates empty for "
        "a missing host directory, reproduces the permanent 503 this "
        "arrangement exists to remove. That mount belongs in "
        "docker-compose.dev.yml only, as an explicit opt-in overlay."
    )


def test_the_dev_overlay_bind_mounts_the_model_path_read_only() -> None:
    compose_dev = COMPOSE_DEV.read_text(encoding="utf-8")

    assert f"{MODEL_MOUNT_MARKER}:ro" in compose_dev, (
        "docker-compose.dev.yml should mount a retrained model read-only at "
        "the same path backend/Dockerfile reads."
    )


def test_the_model_mount_path_agrees_across_the_files_that_share_it() -> None:
    backend_dockerfile = BACKEND_DOCKERFILE.read_text(encoding="utf-8")
    model_dockerfile = MODEL_DOCKERFILE.read_text(encoding="utf-8")
    compose_dev = COMPOSE_DEV.read_text(encoding="utf-8")

    # backend/Dockerfile both copies the model image's output there and
    # points NER_MODEL_NAME at exactly the same path.
    assert "COPY --from=model /models /app/models" in backend_dockerfile
    assert "ENV NER_MODEL_NAME=/app/models/" in backend_dockerfile

    # Dockerfile.model is the other end of that COPY --from: it must publish
    # at /models, the source path backend/Dockerfile names.
    assert "COPY models /models" in model_dockerfile

    # The dev overlay shadows the same destination the backend Dockerfile
    # writes to and reads from, not a path that has quietly drifted from it.
    assert MODEL_MOUNT_MARKER in compose_dev
