# SonicVale (音谷) Agent Guide

> This document is for AI agents working on the SonicVale project. It provides essential context about the codebase architecture, conventions, and development patterns.

## Project Overview

**轻语云配 (SonicVale/音谷)** is an AI-powered multi-character, multi-emotion dubbing platform for novels, scripts, and video content.

- **Frontend**: Vue 3 + Element Plus + Electron (desktop wrapper)
- **Backend**: FastAPI + Python + SQLAlchemy (SQLite)
- **TTS Engines**: IndexTTS-2 (local), Volcano Engine (火山引擎), Alibaba Cloud (阿里云/Bailian)
- **Voice Cloning**: Volcano Engine, Alibaba Cloud (DashScope SDK)
- **LLM**: OpenAI-compatible API for dialogue/line splitting

## Directory Structure

```
SonicVale/
├── SonicVale/                    # Backend (Python FastAPI)
│   ├── app/
│   │   ├── core/                 # Core engines: TTS, LLM, audio, subtitle, WebSocket
│   │   │   ├── subtitle/         # ASR subtitle engines (Bcut, JianYing, Whisper, etc.)
│   │   │   ├── aliyun_tts_client.py          # Alibaba Cloud CosyVoice TTS (DashScope SDK)
│   │   │   ├── aliyun_voice_clone_client.py  # Alibaba Cloud voice cloning (DashScope SDK)
│   │   │   ├── volcano_tts_client.py         # Volcano Engine TTS WebSocket V3 client
│   │   │   ├── volcano_voice_clone_client.py # Volcano Engine voice cloning client
│   │   │   ├── volcano_voice_manager_client.py # Volcano Engine voice management client
│   │   │   ├── tts_engine.py                 # TTS engine orchestrator
│   │   │   ├── tts_runtime.py                # Async TTS worker queue
│   │   │   ├── llm_engine.py                 # LLM dialogue engine
│   │   │   ├── text_correct_engine.py        # Text correction engine
│   │   │   ├── audio_engin.py                # Audio processing (ffmpeg)
│   │   │   ├── ws_manager.py                 # WebSocket connection manager
│   │   │   ├── config.py                     # App configuration paths
│   │   │   ├── enums.py                      # Task enums
│   │   │   ├── prompts.py                    # Prompt templates
│   │   │   └── response.py                   # Standard response model Res[T]
│   │   ├── db/
│   │   │   └── database.py       # SQLAlchemy engine, session, Base
│   │   ├── models/               # ORM PO (Persistent Objects)
│   │   │   ├── po.py             # Main ORM models (Project, Role, Voice, Line, etc.)
│   │   │   └── voice_clone_po.py # VoiceClonePO model
│   │   ├── dto/                  # Data Transfer Objects (Pydantic validation)
│   │   ├── entity/               # Business entity classes (ORM + business layer bridge)
│   │   ├── repositories/         # Database access layer (one per entity)
│   │   ├── services/             # Business logic layer
│   │   ├── routers/              # FastAPI route handlers
│   │   ├── main.py               # FastAPI app entry point
│   │   └── requirements.txt      # Python dependencies
│   └── tests/                    # Backend tests
├── sonicvale-front/              # Frontend (Vue 3 + Element Plus + Electron)
│   ├── src/
│   │   ├── api/                  # API request modules
│   │   ├── pages/                # Vue page components
│   │   ├── components/           # Reusable Vue components (WaveCellPro.vue)
│   │   ├── router/               # Vue Router configuration
│   │   ├── utils/                # Utility functions
│   │   └── assets/               # Static assets
│   ├── electron/                 # Electron main process
│   ├── package.json
│   └── vite.config.js
└── zip归档/                      # Change archive directory
```

## Architecture Layers

The backend follows a clear layered architecture:

```
Routers (API) → Services (Business Logic) → Repositories (DB Access) → ORM Models (PO)
```

### 1. ORM Models (`models/po.py`, `models/voice_clone_po.py`)

Persistent Objects (PO) using SQLAlchemy. Key models:

| Model | Table | Description |
|-------|-------|-------------|
| `ProjectPO` | `projects` | Dubbing projects (with prompt_id, is_precise_fill, project_root_path) |
| `RolePO` | `roles` | Character roles per project |
| `VoicePO` | `voices` | Voice samples (reference audio) |
| `MultiEmotionVoicePO` | `multi_emotion` | Per-emotion voice samples |
| `ChapterPO` | `chapters` | Novel chapters |
| `LinePO` | `lines` | Dialogue lines with emotion/strength, is_done status |
| `EmotionPO` | `emotions` | Emotion types (高兴, 生气, etc.) |
| `StrengthPO` | `strengths` | Strength levels (微弱, 中等, etc.) |
| `LLMProviderPO` | `llm_provider` | LLM API configurations (with custom_params JSON) |
| `TTSProviderPO` | `tts_provider` | TTS provider configs (with provider_type, x_api_key, access_key_id, access_key_secret, voice_type, resource_id, voice_clone_appid) |
| `PromptPO` | `prompts` | System prompts for LLM |
| `VoiceClonePO` | `voice_clones` | Voice cloning records (with name, speaker_id, model_type, language, status, demo_audio_url, version) |

### 2. Entities (`entity/`)

Business entity classes that bridge ORM and service layer. Each entity mirrors a PO but is used in business logic.

### 3. Repositories (`repositories/`)

Thin database access layer. One repository per entity. Methods: `create`, `get_by_id`, `update`, `delete`, `get_by_xxx`.

### 4. Services (`services/`)

Core business logic. Services receive entities, use repositories for persistence, and return entities or DTOs.

### 5. Routers (`routers/`)

FastAPI route handlers. Handle HTTP requests, call services, return `Res` responses.

### 6. Core (`core/`)

Low-level engines: TTS clients, LLM engine, audio processing, WebSocket, async queue.

## Key Conventions

### Response Format

All API endpoints return `Res[T]` from `app.core.response`:

```python
from app.core.response import Res

return Res(data=result, code=200, message="success")
return Res(data=None, code=400, message="error message")
```

### Dependency Injection

Services are created via `Depends(get_service)` pattern:

```python
def get_service(db: Session = Depends(get_db)) -> SomeService:
    repo = SomeRepository(db)
    return SomeService(repo)
```

### Database Migrations

SQLite doesn't support complex migrations. New columns are added dynamically at startup in `main.py`:

```python
def add_xxx_column():
    with engine.begin() as conn:
        result = conn.execute(text("PRAGMA table_info(table_name)"))
        columns = [row[1] for row in result.fetchall()]
        if "new_column" not in columns:
            conn.execute(text("ALTER TABLE table_name ADD COLUMN new_column TEXT"))
```

Current migration history (version tags in `main.py`):
- v1.0.6: `lines.is_done`
- v1.0.7: `llm_provider.custom_params`, `projects.is_precise_fill`, `projects.project_root_path`
- v1.0.8: `tts_provider.provider_type`, `tts_provider.voice_type`
- v1.0.9: `tts_provider.x_api_key`, `voice_clones` table creation
- v1.0.10: `tts_provider.voice_clone_appid`
- v1.0.11: `tts_provider.access_key_id`, `tts_provider.access_key_secret`
- v1.0.12: `tts_provider.resource_id`

### Error Handling

- `ValueError` → HTTP 400 (bad request)
- Other exceptions → HTTP 500 (internal error)
- Use `logging.exception()` for error logging

## TTS Provider Types

The `TTSProviderPO.provider_type` field supports:

| Value | Description | Client | Auth Fields |
|-------|-------------|--------|-------------|
| `index_tts` | Local IndexTTS-2 engine | `tts_engine.py` | api_key |
| `volcano` | Volcano Engine WebSocket TTS V3 | `volcano_tts_client.py` | api_key, x_api_key, access_key_id, access_key_secret |
| `aliyun` | Alibaba Cloud CosyVoice (DashScope SDK) | `aliyun_tts_client.py` | api_key (DashScope API Key) |

Additional TTS provider fields:
- `voice_type`: Speaker/voice identifier (e.g., volcano speaker ID, aliyun default voice name or cloned voice_id)
- `api_base_url`: For `aliyun` type, stores the CosyVoice model name (e.g., `cosyvoice-v3-plus`); for `index_tts`, stores the service URL; for `volcano`, unused
- `resource_id`: Volcano Engine resource ID (seed-tts-2.0 / seed-tts-1.0 / seed-icl-2.0)
- `voice_clone_appid`: AppID for voice cloning service

## Voice Cloning

Two providers support voice cloning:

| Provider | SDK/Protocol | Auth | Features |
|----------|-------------|------|----------|
| Volcano Engine | HTTP REST API | x_api_key, access_key_id, access_key_secret | Upload audio, train, query status |
| Alibaba Cloud | DashScope SDK | api_key (DashScope API Key) | create_voice, list_voice, query_voice, update_voice, delete_voice |

VoiceClonePO tracks cloning records with fields: `tts_provider_id`, `name`, `speaker_id`, `reference_path`, `model_type`, `language`, `status`, `description`, `demo_audio_url`, `version`.

### Alibaba Cloud Voice Cloning → TTS Synthesis Chain

The full chain from voice cloning to TTS synthesis uses a unified DashScope API Key:

```
VoiceCloneManager.vue → aliyun_voice_clone.js → /aliyun-voices/* → AliyunVoiceCloneService
    → AliyunVoiceCloneClient (VoiceEnrollmentService) → DashScope API
    → synced voices stored in VoicePO with name = voice_id

ProjectDubbingDetail.vue → tts_runtime.py (passes voice.name as voice_name)
    → LineService.generate_audio(voice_name=voice_id)
    → _generate_with_aliyun() → AliyunTTSClient (SpeechSynthesizer) → DashScope API
```

**Critical rules for aliyun CosyVoice integration:**
1. **Unified auth**: Both voice cloning (`AliyunVoiceCloneClient`) and TTS synthesis (`AliyunTTSClient`) use the same DashScope `api_key` (set via `dashscope.api_key`). Do NOT use `AccessKeyId:AccessKeySecret` format for aliyun.
2. **Model must match**: The `target_model` used in `create_voice()` must match the `model` used in `SpeechSynthesizer`. The model is configured in `TTSProviderPO.api_base_url` (defaults to `cosyvoice-v3-plus`).
3. **Voice ID passing**: `tts_runtime.py` passes `voice.name` (which is the cloned `voice_id` for aliyun) to `LineService.generate_audio()` via the `voice_name` keyword argument. For aliyun, `voice.name` is the voice_id, not a display name.
4. **Supported models**: `cosyvoice-v3-plus`, `cosyvoice-v3.5-plus`, `cosyvoice-v3.5-flash`, `cosyvoice-v3-flash`.

### Entity-PO Alignment Rule

Every Entity dataclass in `entity/` **must** include all columns from its corresponding PO in `models/po.py`. The service layer converts PO→Entity via `Entity(**{k: v for k, v in po.__dict__.items() if not k.startswith("_")})`, so missing fields cause a `TypeError` at runtime. Always add new PO columns to the matching Entity as well.

## Development Workflow

### Start Backend

```bash
cd SonicVale/SonicVale
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8200
```

### Start Frontend

```bash
cd SonicVale/sonicvale-front
npm install
npm run start
```

### Adding a New Feature

1. **ORM Model** (if new table): Add to `models/po.py` or create new `models/xxx_po.py`
2. **Entity**: Create in `entity/xxx_entity.py`
3. **Repository**: Create in `repositories/xxx_repository.py`
4. **Service**: Create in `services/xxx_service.py`
5. **DTO**: Create in `dto/xxx_dto.py` (Pydantic models)
6. **Router**: Create in `routers/xxx_router.py`, register in `main.py`
7. **Frontend API**: Create in `sonicvale-front/src/api/xxx.js`
8. **Frontend Page**: Create in `sonicvale-front/src/pages/xxx.vue`

### Code Style

- Backend: Python, follow PEP 8
- Frontend: Vue 3 Composition API with `<script setup>`, Element Plus components
- No excessive comments; keep code self-explanatory
- Use Chinese for user-facing messages and UI text

## Important Files Reference

| File | Purpose |
|------|---------|
| `app/main.py` | FastAPI entry, startup/shutdown, route registration, DB migration |
| `app/core/response.py` | Standard response model `Res[T]` |
| `app/core/config.py` | Configuration paths (user dir: ~/SonicVale, ffmpeg path) |
| `app/core/enums.py` | Task enums (TaskEnum) |
| `app/core/prompts.py` | Default prompt templates |
| `app/db/database.py` | SQLAlchemy setup, `get_db()` |
| `app/core/ws_manager.py` | WebSocket manager for progress updates |
| `app/core/tts_runtime.py` | Async TTS worker, passes `voice.name` as `voice_name` to `generate_audio()` |
| `app/core/aliyun_tts_client.py` | Alibaba Cloud CosyVoice TTS via DashScope SpeechSynthesizer |
| `app/core/aliyun_voice_clone_client.py` | Alibaba Cloud voice cloning via DashScope VoiceEnrollmentService |
| `app/services/line_service.py` | Core dubbing logic, dispatches TTS by provider_type (index_tts/volcano/aliyun) |
| `sonicvale-front/src/router/index.js` | Frontend routes (hash history) |
| `sonicvale-front/src/api/config.js` | Axios base URL configuration |

## Current Pages

| Page | Route | Description |
|------|-------|-------------|
| `ProjectList.vue` | `/projects` | Project list |
| `ProjectDubbingDetail.vue` | `/projects/:id/dubbing` | Project detail & dubbing |
| `ConfigCenter.vue` | `/config` | LLM & TTS configuration |
| `VoiceManager.vue` | `/voices` | Voice management (local + cloud) |
| `VoiceCloneManager.vue` | `/voice-clones` | Voice cloning (Volcano + Aliyun) |
| `PromptManager.vue` | `/prompts` | Prompt management |

## Frontend API Modules

| Module | File | Description |
|--------|------|-------------|
| Project | `project.js` | Project CRUD |
| Chapter | `chapter.js` | Chapter management |
| Line | `line.js` | Line/dialogue management |
| Role | `role.js` | Role management |
| Voice | `voice.js` | Voice sample management |
| MultiEmotionVoice | `multiEmotionVoice.js` | Multi-emotion voice management |
| Provider | `provider.js` | LLM & TTS provider management |
| Prompt | `prompt.js` | Prompt management |
| Config | `config.js` | Axios base URL config |
| Enums | `enums.js` | Frontend enum constants |
| VoiceClone | `voice_clone.js` | Voice cloning API |
| AliyunVoiceClone | `aliyun_voice_clone.js` | Alibaba Cloud voice cloning API |
| VolcanoVoice | `volcano_voice.js` | Volcano Engine voice management API |

## Frontend Components

| Component | Description |
|-----------|-------------|
| `WaveCellPro.vue` | Waveform audio player/editor component |

## Dependencies

Key backend dependencies (from `requirements.txt`):
- `fastapi>=0.115.0`, `uvicorn>=0.32.0`, `starlette>=0.41.0` - Web framework
- `sqlalchemy>=2.0.36` - ORM
- `pydantic>=2.10.0` - Data validation
- `openai>=1.50.0` - LLM client
- `dashscope>=1.22.0` - Alibaba Cloud SDK
- `numba>=0.61.0`, `numpy>=2.1.0` - Numerical computing
- `soundfile>=0.13.0` - Audio file I/O
- `openpyxl>=3.1.5` - Excel file support
- `pypinyin>=0.53.0` - Chinese pinyin conversion
- `requests>=2.32.0` - HTTP client
- `websocket-client>=1.8.0` - WebSocket client

Frontend dependencies:
- `vue@3`, `vue-router@4`, `element-plus` - UI framework
- `electron` - Desktop wrapper
- `axios` - HTTP client
- `wavesurfer.js` - Audio waveform visualization
- `sortablejs` - Drag-and-drop sorting
- `vue-virtual-scroll-list` - Virtual scrolling for large lists
- `vue-json-pretty` - JSON display component
- `vue-json-editor` - JSON editing component
- `iconv-lite` - Character encoding conversion
- `electron-log` - Electron logging
- `@playwright/test` - E2E testing

## Startup Initialization

On startup, `main.py` performs:
1. **Database migration**: Creates tables, adds missing columns
2. **Runtime setup**: Initializes async TTS queue and thread pool
3. **Background workers**: Starts TTS worker tasks
4. **Default data**: Creates default TTS provider, emotions (10 types), strengths (5 levels), and default prompt
5. **Data migration**: Updates existing projects' `project_root_path` if missing
