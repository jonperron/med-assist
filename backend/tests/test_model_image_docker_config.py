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


def test_the_dev_overlay_requires_model_dir_rather_than_defaulting_it() -> None:
    """A default here is how you mount an empty directory over good weights.

    `${MODEL_DIR:-./backend/models}` silently substitutes a path that may not
    exist; Docker then creates it empty and it shadows the baked-in weights
    just as well as a full directory would. `:?` fails the command instead.
    This is the exact line the superseded arrangement shipped, so a regression
    to it is a plausible edit rather than a hypothetical one.
    """
    compose_dev = COMPOSE_DEV.read_text(encoding="utf-8")

    assert "${MODEL_DIR:?" in compose_dev, (
        "docker-compose.dev.yml must require MODEL_DIR with `:?`, not "
        "default it with `:-`."
    )
    assert (
        "${MODEL_DIR:-" not in compose_dev
    ), "docker-compose.dev.yml must not give MODEL_DIR a default value."


def test_the_image_keeps_the_hub_switched_off() -> None:
    """The offline guarantee has to travel with the image, not with compose.

    `NER_MODEL_NAME` is an environment variable, so any deployment can point
    it at a Hub id - and that is the obvious way to "fix" an unready
    container. Without these three set in the image, transformers would fetch
    it over the network, from a service whose whole claim is that clinical
    documents do not leave the machine. Baking the weights back in does not
    make them redundant, and nothing else enforces their presence.
    """
    backend_dockerfile = BACKEND_DOCKERFILE.read_text(encoding="utf-8")

    for variable in (
        "HF_HUB_OFFLINE=1",
        "TRANSFORMERS_OFFLINE=1",
        "HF_HUB_DISABLE_TELEMETRY=1",
    ):
        assert variable in backend_dockerfile, (
            f"backend/Dockerfile must set {variable}. The offline refusal "
            "travels with the image so that a `docker run` which never reads "
            "a compose file still cannot reach the Hub."
        )


def test_the_model_image_carries_no_source_label() -> None:
    """A source label auto-links the package to this public repository.

    On GHCR a linked package takes the visibility of the repository it is
    linked to, and this repository is public. The weights are DrBERT
    fine-tuned on a clinical corpus that is not distributable, so a label
    here would flip a private package public on the next push. Today the
    prohibition exists only as a comment in the file.
    """
    model_dockerfile = MODEL_DOCKERFILE.read_text(encoding="utf-8")
    directives = [
        line.strip()
        for line in model_dockerfile.splitlines()
        if not line.lstrip().startswith("#")
    ]

    assert not any("org.opencontainers.image.source" in line for line in directives), (
        "backend/Dockerfile.model must not declare "
        "org.opencontainers.image.source: it links the package to this "
        "public repository on GHCR and makes the weights public with it."
    )
