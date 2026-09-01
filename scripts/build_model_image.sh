#!/usr/bin/env bash
#
# Build the model image: the NER weights, and nothing else, as an OCI image.
#
#   scripts/build_model_image.sh                       # -> med-assist-model:local
#   scripts/build_model_image.sh 1.0                   # -> med-assist-model:1.0
#   MODEL_DIR=/srv/weights scripts/build_model_image.sh 1.0
#
# The backend image consumes the result as a build stage, so the weights reach
# a deployment through a registry rather than through a directory on the build
# host. That is what makes the backend buildable from a Git clone: the clone
# carries no weights, backend/models/ being gitignored and ~420MB.
#
# ---------------------------------------------------------------------------
# THE REGISTRY MUST BE PRIVATE - AND SO MUST ANY BACKEND IMAGE BUILT FROM IT
# ---------------------------------------------------------------------------
# The model is Dr-BERT/DrBERT-7GB fine-tuned on the DEFT 2021 corpus of French
# clinical cases. The corpus is not distributable - that alone is sufficient and
# is not in doubt. On top of it, the possibility that fine-tuned weights carry
# memorised spans of their training data cannot be ruled out, and the training
# data here is clinical text about real people. So publishing this image is a
# data-protection problem, not a licensing footnote, and unlike a licensing
# mistake it cannot be undone: whoever pulled it keeps it.
#
# This applies to the BACKEND image too. `backend/Dockerfile` copies /models out
# of this image, so a backend image built against it contains the same bytes and
# inherits the same constraint. Neither may be pushed to a public package. See
# .github/workflows/docker_build.yml.
#
# There is no push flag on purpose. This script builds, verifies and prints;
# a person runs the push. Adding a flag that pushes is a decision entry.
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
version="${1:-local}"
model_dir="${MODEL_DIR:-${repo_root}/backend/models}"
image_name="${MODEL_IMAGE_NAME:-med-assist-model}"
tag="${image_name}:${version}"

# What `from_pretrained` needs. Absent any of these, the backend loads nothing.
required_files=(config.json model.safetensors tokenizer.json tokenizer_config.json)

# What may travel alongside them. This is an allowlist, and the image is built
# from it rather than from whatever the directory happens to hold - which is the
# point. MODEL_DIR is documented as pointing anywhere, so it can be aimed at a
# training run's output directory, and those hold checkpoint-*/, runs/ event
# files and evaluation prediction dumps. A prediction dump over this corpus
# contains corpus text. Copying a directory wholesale would put that in a
# published image, and neither the file-presence check nor the size check below
# would notice, because both only ever ask whether there is enough, never
# whether there is too much.
#
# metrics.json is here because the training project writes it beside the weights
# and it is a page of scores. Anything not on either list stops the build rather
# than being silently dropped: a file that belongs to the model must be added
# here deliberately, by someone who has looked at what is in it.
optional_files=(
  metrics.json
  special_tokens_map.json
  vocab.txt
  merges.txt
  added_tokens.json
  preprocessor_config.json
)

if [[ ! -d "${model_dir}" ]]; then
  echo "error: no such directory: ${model_dir}" >&2
  echo "       set MODEL_DIR to where the weights are." >&2
  exit 1
fi

missing=()
for name in "${required_files[@]}"; do
  [[ -f "${model_dir}/${name}" ]] || missing+=("${name}")
done
if (( ${#missing[@]} > 0 )); then
  echo "error: ${model_dir} is not a model directory; missing: ${missing[*]}" >&2
  exit 1
fi

# Refuse anything unrecognised rather than shipping or silently dropping it.
allowed=("${required_files[@]}" "${optional_files[@]}")
unexpected=()
while IFS= read -r entry; do
  name="$(basename "${entry}")"
  known=""
  for candidate in "${allowed[@]}"; do
    [[ "${name}" == "${candidate}" ]] && known=1 && break
  done
  [[ -n "${known}" ]] || unexpected+=("${name}")
done < <(find "${model_dir}" -mindepth 1 -maxdepth 1 | sort)

if (( ${#unexpected[@]} > 0 )); then
  echo "error: ${model_dir} holds entries this script does not recognise:" >&2
  printf '         %s\n' "${unexpected[@]}" >&2
  echo "       This image gets published. A training run's output directory" >&2
  echo "       holds checkpoints and prediction dumps, and a prediction dump" >&2
  echo "       over this corpus contains clinical text." >&2
  echo "       Point MODEL_DIR at a directory holding only the model, or add" >&2
  echo "       the entry to optional_files in this script once you have looked" >&2
  echo "       at what is in it." >&2
  exit 1
fi

# Stage the allowlisted files into a context of their own. Always, with no
# same-directory shortcut, so there is exactly one code path and the published
# image is built from the allowlist rather than from a directory listing.
#
# File by file, never `cp -r` of the directory: `cp -rl src dst` creates dst
# before it fails, so a cross-filesystem fallback of `cp -r src dst` copies the
# source *into* it and yields models/<dirname>/config.json. That nests silently,
# passes the size check below with room to spare, and produces a backend image
# whose /app/models has no config.json - the permanent 503 this whole
# arrangement exists to remove. Reproduced before it was written out.
#
# Hard link where the filesystem allows it, copy where it does not:
# model.safetensors is ~420MB and staging it should not be a round trip. Set
# TMPDIR to the filesystem holding the weights to keep it in the link path.
staged="$(mktemp -d)"
# shellcheck disable=SC2064  # expand staged now, not when the trap fires
trap "rm -rf '${staged}'" EXIT INT TERM
mkdir -p "${staged}/models"
cp "${repo_root}/backend/Dockerfile.model" "${staged}/"
cp "${repo_root}/backend/Dockerfile.model.dockerignore" "${staged}/"

staged_names=()
for name in "${allowed[@]}"; do
  [[ -f "${model_dir}/${name}" ]] || continue
  cp -l "${model_dir}/${name}" "${staged}/models/${name}" 2>/dev/null \
    || cp "${model_dir}/${name}" "${staged}/models/${name}"
  staged_names+=("${name}")
done

echo "building ${tag} from ${model_dir}"
echo "  including: ${staged_names[*]}"

# Build to a temporary tag and promote only once it verifies, so that a failed
# rerun cannot destroy a good image left by an earlier one. Deleting ${tag} on
# failure would do exactly that, and the next backend build would then try to
# pull med-assist-model:local from Docker Hub.
build_tag="${image_name}:build-$$"
DOCKER_BUILDKIT=1 docker build \
  --file "${staged}/Dockerfile.model" \
  --tag "${build_tag}" \
  "${staged}"

# A backstop, not the primary guard. The primary guard is BuildKit itself: with
# models/ excluded, `COPY models /models` fails the build with
# `"/models": not found` and names the .dockerignore line - verified, it is loud
# rather than silent. This catches the residue - an allowlist that matched
# nothing but the small JSON files, a truncated safetensors - for the price of
# one `docker image inspect`. There is no cheaper way to look inside: the image
# is FROM scratch, so it has no shell for `docker run` and no command for
# `docker create`.
echo "verifying ${build_tag}"
size_bytes="$(docker image inspect "${build_tag}" --format '{{.Size}}')"
if (( size_bytes < 100000000 )); then
  echo "error: ${build_tag} is ${size_bytes} bytes - the weights are not in it." >&2
  docker image rm "${build_tag}" >/dev/null 2>&1 || true
  exit 1
fi

docker tag "${build_tag}" "${tag}"
docker image rm "${build_tag}" >/dev/null 2>&1 || true
echo "ok: ${tag} is ${size_bytes} bytes"

cat <<EOF

Built ${tag}. It is local; nothing has been pushed.

To use it locally, set this in .env:

    MODEL_IMAGE=${tag}

------------------------------------------------------------------------------
To publish it - PRIVATE REGISTRY ONLY. Read the header of this script first.
------------------------------------------------------------------------------
The hazard is that a GHCR package linked to a public repository is public, and a
package gets linked automatically when it is pushed by CI with GITHUB_TOKEN or
when the image carries an org.opencontainers.image.source label. A manually
pushed, unlinked user-scoped package is created private - but "probably private"
is not a basis for publishing clinical-derived weights. So create the package
with an image that holds nothing, confirm it is private, and only then push the
weights. At no point is the model image the thing that creates the package.

    # 1. Create the package with a weightless placeholder.
    docker pull hello-world:latest
    docker tag hello-world:latest ghcr.io/jonperron/med-assist-model:bootstrap
    docker push ghcr.io/jonperron/med-assist-model:bootstrap

    # 2. Set it Private, at
    #    https://github.com/users/jonperron/packages/container/med-assist-model/settings
    #    then CONFIRM before going any further:
    gh api /user/packages/container/med-assist-model --jq .visibility
    #    Do not continue unless this prints: private

    # 3. Only now push the weights.
    docker tag ${tag} ghcr.io/jonperron/med-assist-model:${version}
    docker push ghcr.io/jonperron/med-assist-model:${version}

    # 4. Confirm again, and remove the placeholder.
    gh api /user/packages/container/med-assist-model --jq .visibility

Give the deployment a read-only credential for that package: a token scoped to
read:packages and nothing more, supplied with
\`docker login ghcr.io --password-stdin\`, or stored in the deployment
platform's registry-credential store. Never as a --build-arg and never as an
ENV - both are readable afterwards with \`docker history\`. Never in .env.

Then set MODEL_IMAGE to the pushed reference. Retraining means a new version
tag, never a moved one: the backend image's digest covers the weights only if
the tag it was built against does not change under it.

Remember that the backend image built from this one contains the weights too,
and is equally not publishable.
EOF
