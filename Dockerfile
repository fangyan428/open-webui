# Initialize device type args
# use build args in the docker build command with --build-arg="BUILDARG=true"
ARG USE_CUDA=false
ARG USE_OLLAMA=false
ARG USE_SLIM=false
ARG USE_PERMISSION_HARDENING=false
# Tested with cu117 for CUDA 11 and cu121 for CUDA 12 (default)
ARG USE_CUDA_VER=cu128
# any sentence transformer model; models to use can be found at https://huggingface.co/models?library=sentence-transformers
# Leaderboard: https://huggingface.co/spaces/mteb/leaderboard 
# for better performance and multilangauge support use "intfloat/multilingual-e5-large" (~2.5GB) or "intfloat/multilingual-e5-base" (~1.5GB)
# IMPORTANT: If you change the embedding model (sentence-transformers/all-MiniLM-L6-v2) and vice versa, you aren't able to use RAG Chat with your previous documents loaded in the WebUI! You need to re-embed them.
ARG USE_EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
ARG USE_RERANKING_MODEL=""
ARG USE_AUXILIARY_EMBEDDING_MODEL=TaylorAI/bge-micro-v2

# Tiktoken encoding name; models to use can be found at https://huggingface.co/models?library=tiktoken
ARG USE_TIKTOKEN_ENCODING_NAME="cl100k_base"

ARG BUILD_HASH=dev-build
# Override at your own risk - non-root configurations are untested
ARG UID=0
ARG GID=0

######## WebUI frontend ########
FROM --platform=$BUILDPLATFORM node:22-alpine3.20 AS build
ARG ALPINE_MIRROR=https://dl-cdn.alpinelinux.org/alpine
ARG BUILD_HASH
ARG NPM_CONFIG_REGISTRY=https://registry.npmjs.org

# This stage only compiles the Web UI. onnxruntime-node otherwise assumes CUDA
# 12 when nvcc is absent and downloads an unused GPU runtime from GitHub.
ENV ONNXRUNTIME_NODE_INSTALL_CUDA=skip

WORKDIR /app

# to store git revision in build
RUN set -e; \
    sed -i "s|https://dl-cdn.alpinelinux.org/alpine|${ALPINE_MIRROR}|g" /etc/apk/repositories; \
    for attempt in 1 2 3 4 5; do \
    if apk add --no-cache git; then break; fi; \
    if [ "$attempt" -eq 5 ]; then exit 1; fi; \
    echo "apk add failed (attempt $attempt/5); retrying..."; \
    sleep 2; \
    done

COPY package.json package-lock.json ./
RUN set -e; \
    for attempt in 1 2 3 4 5; do \
    if npm ci --force; then break; fi; \
    if [ "$attempt" -eq 5 ]; then exit 1; fi; \
    echo "npm ci failed (attempt $attempt/5); retrying..."; \
    sleep 2; \
    done

COPY . .
ENV APP_BUILD_HASH=${BUILD_HASH}
ARG NODE_MAX_OLD_SPACE_SIZE=8192
RUN NODE_OPTIONS="--max-old-space-size=${NODE_MAX_OLD_SPACE_SIZE}" npm run build

######## WebUI backend ########
FROM python:3.11-slim-bookworm AS base

# Use args
ARG USE_CUDA
ARG USE_OLLAMA
ARG USE_CUDA_VER
ARG USE_SLIM
ARG USE_PERMISSION_HARDENING
ARG USE_EMBEDDING_MODEL
ARG USE_RERANKING_MODEL
ARG USE_AUXILIARY_EMBEDDING_MODEL
ARG UID
ARG GID
ARG DEBIAN_MIRROR=http://deb.debian.org
ARG HF_ENDPOINT=https://huggingface.co
ARG HF_HUB_DISABLE_XET=false
ARG PIP_INDEX_URL
ARG PYTORCH_CPU_INDEX_URL=https://download.pytorch.org/whl/cpu
ARG TIKTOKEN_TOKENIZER_URL
ARG UV_INDEX_URL

# Python settings
ENV PYTHONUNBUFFERED=1

## Basis ##
ENV ENV=prod \
    PORT=8080 \
    # pass build args to the build
    USE_OLLAMA_DOCKER=${USE_OLLAMA} \
    USE_CUDA_DOCKER=${USE_CUDA} \
    USE_SLIM_DOCKER=${USE_SLIM} \
    USE_CUDA_DOCKER_VER=${USE_CUDA_VER} \
    USE_EMBEDDING_MODEL_DOCKER=${USE_EMBEDDING_MODEL} \
    USE_RERANKING_MODEL_DOCKER=${USE_RERANKING_MODEL} \
    USE_AUXILIARY_EMBEDDING_MODEL_DOCKER=${USE_AUXILIARY_EMBEDDING_MODEL}

## Basis URL Config ##
ENV OLLAMA_BASE_URL="/ollama" \
    OPENAI_API_BASE_URL=""

## API Key and Security Config ##
ENV OPENAI_API_KEY="" \
    WEBUI_SECRET_KEY="" \
    SCARF_NO_ANALYTICS=true \
    DO_NOT_TRACK=true \
    ANONYMIZED_TELEMETRY=false

#### Other models #########################################################
## whisper TTS model settings ##
ENV WHISPER_MODEL="base" \
    WHISPER_MODEL_DIR="/app/backend/cache-seed/whisper/models"

## RAG Embedding model settings ##
ENV RAG_EMBEDDING_MODEL="$USE_EMBEDDING_MODEL_DOCKER" \
    RAG_RERANKING_MODEL="$USE_RERANKING_MODEL_DOCKER" \
    AUXILIARY_EMBEDDING_MODEL="$USE_AUXILIARY_EMBEDDING_MODEL_DOCKER" \
    SENTENCE_TRANSFORMERS_HOME="/app/backend/cache-seed/embedding/models"

## Tiktoken model settings ##
ENV TIKTOKEN_ENCODING_NAME="cl100k_base" \
    TIKTOKEN_CACHE_DIR="/app/backend/cache-seed/tiktoken"

## Hugging Face download cache ##
ENV HF_HOME="/app/backend/cache-seed/embedding/models"

## Torch Extensions ##
# ENV TORCH_EXTENSIONS_DIR="/.cache/torch_extensions"

#### Other models ##########################################################

WORKDIR /app/backend

ENV HOME=/root
# Create user and group if not root
RUN if [ $UID -ne 0 ]; then \
    if [ $GID -ne 0 ]; then \
    addgroup --gid $GID app; \
    fi; \
    adduser --uid $UID --gid $GID --home $HOME --disabled-password --no-create-home app; \
    fi

RUN mkdir -p $HOME/.cache/chroma
RUN echo -n 00000000-0000-0000-0000-000000000000 > $HOME/.cache/chroma/telemetry_user_id

# Make sure the user has access to the app and root directory
RUN chown -R $UID:$GID /app $HOME

# Install common system dependencies
RUN set -e; \
    sed -i "s|http://deb.debian.org|${DEBIAN_MIRROR}|g" /etc/apt/sources.list.d/debian.sources; \
    for attempt in 1 2 3 4 5; do \
    if apt-get -o Acquire::Retries=5 update && \
    apt-get -o Acquire::Retries=5 install -y --no-install-recommends \
    git build-essential pandoc gcc netcat-openbsd curl jq ca-certificates \
    libmariadb-dev \
    python3-dev \
    ffmpeg libsm6 libxext6 zstd; then \
    break; \
    fi; \
    if [ "$attempt" -eq 5 ]; then exit 1; fi; \
    echo "apt-get install failed (attempt $attempt/5); retrying..."; \
    sleep 2; \
    done; \
    rm -rf /var/lib/apt/lists/*

# install python dependencies
COPY --chown=$UID:$GID ./backend/requirements.txt ./requirements.txt

# Set UV_LINK_MODE to copy to prevent 0-byte file corruption in QEMU arm64 cross-builds
ENV UV_LINK_MODE=copy

RUN set -e; \
    retry() { \
    attempt=1; \
    until "$@"; do \
    if [ "$attempt" -ge 5 ]; then return 1; fi; \
    echo "command failed (attempt $attempt/5); retrying..."; \
    attempt=$((attempt + 1)); \
    sleep 2; \
    done; \
    }; \
    prepare_tiktoken_cache() { \
    if [ -z "${TIKTOKEN_TOKENIZER_URL}" ]; then return 0; fi; \
    retry curl --fail --location --show-error --silent "${TIKTOKEN_TOKENIZER_URL}" -o /tmp/cl100k-tokenizer.json; \
    python -c 'import base64,hashlib,json,os; vocab=json.load(open("/tmp/cl100k-tokenizer.json"))["model"]["vocab"]; visible=list(range(ord("!"),ord("~")+1))+list(range(ord("¡"),ord("¬")+1))+list(range(ord("®"),ord("ÿ")+1)); missing=[b for b in range(256) if b not in visible]; decoder={chr(c):b for b,c in zip(visible+missing,visible+[256+i for i in range(len(missing))])}; rows=sorted((rank,bytes(decoder[ch] for ch in token)) for token,rank in vocab.items() if rank < 100256); data=b"".join(base64.b64encode(token)+b" "+str(rank).encode()+b"\n" for rank,token in rows); expected="223921b76ee99bde995b7ff738513eef100fb51d18c93597a113bcffe865b2a7"; assert len(rows)==100256 and hashlib.sha256(data).hexdigest()==expected; cache=os.environ["TIKTOKEN_CACHE_DIR"]; os.makedirs(cache,exist_ok=True); open(os.path.join(cache,"9b5ad71b2ce5302211f9c61530b329a4922fc6a4"),"wb").write(data)'; \
    rm -f /tmp/cl100k-tokenizer.json; \
    }; \
    retry pip3 install --no-cache-dir uv; \
    if [ "$USE_CUDA" = "true" ]; then \
    # If you use CUDA the whisper and embedding model will be downloaded on first use
    # fix: pin torch<=2.9.1 - torch 2.10.0 aarch64 wheels cause SIGILL on ARM devices (RPi 4 Cortex-A72) #21349
    retry pip3 install 'torch<=2.9.1' torchvision torchaudio --index-url https://download.pytorch.org/whl/$USE_CUDA_DOCKER_VER --no-cache-dir; \
    retry uv pip install --system -r requirements.txt --no-cache-dir; \
    prepare_tiktoken_cache; \
    retry python -c "import os; from sentence_transformers import SentenceTransformer; SentenceTransformer(os.environ['RAG_EMBEDDING_MODEL'], device='cpu')"; \
    retry python -c "import os; from sentence_transformers import SentenceTransformer; SentenceTransformer(os.environ.get('AUXILIARY_EMBEDDING_MODEL', 'TaylorAI/bge-micro-v2'), device='cpu')"; \
    retry python -c "import os; from faster_whisper import WhisperModel; WhisperModel(os.environ['WHISPER_MODEL'], device='cpu', compute_type='int8', download_root=os.environ['WHISPER_MODEL_DIR'])"; \
    retry python -c "import os; import tiktoken; tiktoken.get_encoding(os.environ['TIKTOKEN_ENCODING_NAME'])"; \
    retry python -c "import nltk; nltk.download('punkt_tab')"; \
    else \
    retry pip3 install 'torch<=2.9.1' torchvision torchaudio --index-url "${PYTORCH_CPU_INDEX_URL}" --no-cache-dir; \
    retry uv pip install --system -r requirements.txt --no-cache-dir; \
    prepare_tiktoken_cache; \
    if [ "$USE_SLIM" != "true" ]; then \
    retry python -c "import os; from sentence_transformers import SentenceTransformer; SentenceTransformer(os.environ['RAG_EMBEDDING_MODEL'], device='cpu')"; \
    retry python -c "import os; from sentence_transformers import SentenceTransformer; SentenceTransformer(os.environ.get('AUXILIARY_EMBEDDING_MODEL', 'TaylorAI/bge-micro-v2'), device='cpu')"; \
    retry python -c "import os; from faster_whisper import WhisperModel; WhisperModel(os.environ['WHISPER_MODEL'], device='cpu', compute_type='int8', download_root=os.environ['WHISPER_MODEL_DIR'])"; \
    retry python -c "import os; import tiktoken; tiktoken.get_encoding(os.environ['TIKTOKEN_ENCODING_NAME'])"; \
    retry python -c "import nltk; nltk.download('punkt_tab')"; \
    fi; \
    fi; \
    mkdir -p /app/backend/data; chown -R $UID:$GID /app/backend/data/; \
    rm -rf /var/lib/apt/lists/*;

# Runtime caches live in persistent DATA_DIR. start.sh seeds missing entries
# from the image cache above when a bind mount starts empty.
ENV WHISPER_MODEL_DIR="/app/backend/data/cache/whisper/models" \
    SENTENCE_TRANSFORMERS_HOME="/app/backend/data/cache/embedding/models" \
    TIKTOKEN_CACHE_DIR="/app/backend/data/cache/tiktoken" \
    HF_HOME="/app/backend/data/cache/embedding/models"

# Install Ollama if requested
RUN if [ "$USE_OLLAMA" = "true" ]; then \
    date +%s > /tmp/ollama_build_hash && \
    echo "Cache broken at timestamp: `cat /tmp/ollama_build_hash`" && \
    curl -fsSL https://ollama.com/install.sh | sh && \
    rm -rf /var/lib/apt/lists/*; \
    fi

# copy embedding weight from build
# RUN mkdir -p /root/.cache/chroma/onnx_models/all-MiniLM-L6-v2
# COPY --from=build /app/onnx /root/.cache/chroma/onnx_models/all-MiniLM-L6-v2/onnx

# copy built frontend files
COPY --chown=$UID:$GID --from=build /app/build /app/build
COPY --chown=$UID:$GID --from=build /app/CHANGELOG.md /app/CHANGELOG.md
COPY --chown=$UID:$GID --from=build /app/package.json /app/package.json

# copy backend files
COPY --chown=$UID:$GID ./backend .

# The backend rewrites its bundled static assets (favicons, splash, manifest,
# loader.js, ...) under open_webui/static at startup. Make that directory
# writable by an arbitrary UID -- which under OpenShift's restricted SCC is
# always a member of GID 0 -- so those writes don't fail with EACCES and crash
# the boot log with "[Errno 13] Permission denied". `chmod -R g=u` mirrors the
# owner bits onto the group (the Red Hat arbitrary-UID idiom). This is applied
# unconditionally because it targets a directory the app writes on every start;
# the broader, opt-in USE_PERMISSION_HARDENING below covers the rest of /app.
RUN chgrp -R 0 /app/backend/open_webui/static && \
    chmod -R g=u /app/backend/open_webui/static

EXPOSE 8080

HEALTHCHECK CMD curl --silent --fail http://localhost:${PORT:-8080}/health | jq -ne 'input.status == true' || exit 1

# Minimal, atomic permission hardening for OpenShift (arbitrary UID):
# - Group 0 owns /app and /root
# - Directories are group-writable and have SGID so new files inherit GID 0
RUN if [ "$USE_PERMISSION_HARDENING" = "true" ]; then \
    set -eux; \
    chgrp -R 0 /app /root || true; \
    chmod -R g+rwX /app /root || true; \
    find /app -type d -exec chmod g+s {} + || true; \
    find /root -type d -exec chmod g+s {} + || true; \
    fi

USER $UID:$GID

ARG BUILD_HASH
ENV WEBUI_BUILD_VERSION=${BUILD_HASH}
ENV DOCKER=true

CMD [ "bash", "start.sh"]
