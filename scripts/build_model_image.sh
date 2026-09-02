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
# and it is a page of scores. Anything not on any of these lists stops the build
# rather than being silently dropped: a file that belongs to the model must be
# added here deliberately, by someone who has looked at what is in it.
#
# Both tokenizer vocabularies are listed. DrBERT is RoBERTa-family, so a
# slow-tokenizer save writes vocab.json and merges.txt, not the WordPiece
# vocab.txt - listing only one of them would refuse a legitimate re-save.
optional_files=(
  metrics.json
  special_tokens_map.json
  vocab.json
  vocab.txt
  merges.txt
  added_tokens.json
  preprocessor_config.json
  sentencepiece.bpe.model
  tokenizer.model
)

# Tolerated but never staged. These turn up in any directory fetched from the
# Hub - `huggingface-cli download --local-dir` leaves .cache/, a git clone
# leaves .gitattributes and .git/, and a model card is README.md - and none of
# them belongs in a published image. Kept separate from optional_files because
# that list has two jobs otherwise: permitted-to-exist and gets-shipped. Telling
# someone to add .gitattributes to optional_files would ship it.
ignored_entries=(
  README.md
  .gitattributes
  .gitignore
  .cache
  .git
  .DS_Store
)

if [[ ! -d "${model_dir}" ]]; then
  echo "error: no such directory: ${model_dir}" >&2
  echo "       set MODEL_DIR to where the weights are." >&2
  exit 1
fi

# Resolve symlinks before anything looks inside. `find` does not descend into a
# symlinked starting point, so an un-normalised symlinked MODEL_DIR made the
# scan below emit nothing at all: no entries, no unexpected ones, guard passes
# silently. Meanwhile `[[ -f ]]` does follow symlinks, so staging proceeded
# normally - a guard reporting "clean" for a directory it never opened.
# Symlinking a ~420MB gitignored weights directory is a plausible local setup,
# so this is reachable rather than theoretical.
model_dir="$(cd "${model_dir}" && pwd -P)"

missing=()
for name in "${required_files[@]}"; do
  [[ -f "${model_dir}/${name}" ]] || missing+=("${name}")
done
if (( ${#missing[@]} > 0 )); then
  echo "error: ${model_dir} is not a model directory; missing: ${missing[*]}" >&2
  echo "       Sharded checkpoints are not supported: a model saved above the" >&2
  echo "       shard threshold writes model-00001-of-0000N.safetensors and an" >&2
  echo "       index instead of model.safetensors, and would be reported here." >&2
  exit 1
fi

# Refuse anything unrecognised rather than shipping or silently dropping it.
# -print0 with `read -d ''` because a filename may contain a newline, which the
# line-oriented form silently splits into components that can each look
# allowlisted.
allowed=("${required_files[@]}" "${optional_files[@]}" "${ignored_entries[@]}")
unexpected=()
symlinked=()
while IFS= read -r -d '' entry; do
  name="${entry##*/}"
  # Refuse a symlink rather than follow it. The allowlist validates names, not
  # contents, so an allowlisted name pointing at a prediction dump would satisfy
  # every check in this script and ship the target's bytes under a safe name.
  if [[ -L "${entry}" ]]; then
    symlinked+=("${name}")
    continue
  fi
  known=""
  for candidate in "${allowed[@]}"; do
    [[ "${name}" == "${candidate}" ]] && known=1 && break
  done
  [[ -n "${known}" ]] || unexpected+=("${name}")
done < <(find "${model_dir}" -mindepth 1 -maxdepth 1 -print0)

if (( ${#symlinked[@]} > 0 )); then
  echo "error: ${model_dir} holds symlinks, which this script will not follow:" >&2
  printf '         %s\n' "${symlinked[@]}" >&2
  echo "       The allowlist checks names, not what they point at, so a" >&2
  echo "       permitted name aimed at a prediction dump would ship its bytes." >&2
  echo "       Copy the real files into a directory of their own." >&2
  exit 1
fi

if (( ${#unexpected[@]} > 0 )); then
  echo "error: ${model_dir} holds entries this script does not recognise:" >&2
  printf '         %s\n' "${unexpected[@]}" >&2
  echo "       This image gets published. A training run's output directory" >&2
  echo "       holds checkpoints and prediction dumps, and a prediction dump" >&2
  echo "       over this corpus contains clinical text." >&2
  echo "       Point MODEL_DIR at a directory holding only the model. If an" >&2
  echo "       entry really belongs to the model, add it to optional_files in" >&2
  echo "       this script - which also ships it - once you have looked at" >&2
  echo "       what is in it. To tolerate it without shipping it, add it to" >&2
  echo "       ignored_entries instead." >&2
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
# TMPDIR to the filesystem holding the weights to keep it in the link path -
# and note that on most Linux systems /tmp is tmpfs, so the default with the
# weights on disk takes the copy path and writes ~420MB into RAM. On a small
# machine that is an OOM rather than a slow build.
staged="$(mktemp -d)"
build_tag="${image_name}:build-$$"

# The staging directory AND the temporary tag, on every exit path. Cleaning up
# only the directory left a ~420MB med-assist-model:build-<pid> behind whenever
# the build was interrupted or the inspect failed - an image under a name nobody
# would later recognise. The handler ends in `exit` because a bare trap on
# INT returns to where it was: without it, a signal during the copy loop
# deleted the staging directory and let the loop go on copying into nothing.
cleanup() {
  rm -rf "${staged}"
  docker image rm "${build_tag}" >/dev/null 2>&1 || true
}
trap cleanup EXIT
trap 'cleanup; exit 130' INT
trap 'cleanup; exit 143' TERM
mkdir -p "${staged}/models"
cp "${repo_root}/backend/Dockerfile.model" "${staged}/"
cp "${repo_root}/backend/Dockerfile.model.dockerignore" "${staged}/"

# required + optional only, never ignored_entries: that list exists to tolerate
# a model card or a .gitattributes without putting it in a published image.
stageable=("${required_files[@]}" "${optional_files[@]}")
staged_names=()
for name in "${stageable[@]}"; do
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
  exit 1
fi

# Promote, then let the trap drop the temporary tag on the way out.
docker tag "${build_tag}" "${tag}"
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

    # 4. Confirm again, then remove the placeholder.
    gh api /user/packages/container/med-assist-model --jq .visibility
    gh api /user/packages/container/med-assist-model/versions \
      --jq '.[] | select(.metadata.container.tags[]? == "bootstrap") | .id'
    gh api --method DELETE \
      /user/packages/container/med-assist-model/versions/<id-from-above>

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
