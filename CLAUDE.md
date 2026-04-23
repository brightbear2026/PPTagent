# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a professional PPT generation agent system designed to produce consulting-grade presentations comparable to the Big Four consulting firms (McKinsey, BCG, Bain, Deloitte). The system emphasizes high information density, professional visual design, precise data visualization, and professional technical diagrams.

**Core Goals:**
- Generate professional-grade PPT with transparent, observable automation
- Support multiple input formats (documents, spreadsheets, Markdown, natural language, existing PPT)
- Provide structured content review at 4 mandatory checkpoints
- Quality over speed: 3-10 minute generation time is acceptable

## Architecture

The system uses a **6-layer pipeline architecture** with data flowing through a unified `SlideSpec` data model. Each layer incrementally fills different fields of the SlideSpec object.

### Layer Structure

1. **Layer 1: Input Parser** - Parse multiple input formats (DOCX/XLSX/CSV/PPTX/TXT/MD)
2. **Layer 2: Content Extractor** - Extract structured elements using LLM (facts, data, opinions, conclusions)
3. **Layer 2: Narrative Architect** - Build narrative structure with core arguments and transitions
4. **Layer 3: Structure Planner** - Generate slide-level structure with takeaway messages
5. **Layer 4: Visual Designer** - Assign layout templates and visual themes (rule engine)
6. **Layer 5: Chart Generator** - Generate chart specifications with narrative insights
7. **Layer 6: Layout Engine + PPT Builder** - Calculate precise coordinates and build final .pptx file

### Pipeline Execution Mode

The pipeline runs in **manual mode only** (no auto/step toggle). Execution pauses at 4 mandatory checkpoints where user review and confirmation is required.

**7 Pipeline stages**: `layer1` -> `layer2_extract` -> `layer2_narrative` -> `layer3` -> `layer4` -> `layer5` -> `layer6`

Each stage's result is persisted in `pipeline_stages` SQLite table. Users can edit any completed stage and re-run from that point via `POST /api/task/{id}/resume`.

### 4 Mandatory Checkpoints

The pipeline pauses at these 4 points. User must explicitly confirm before continuing.

| # | Checkpoint | Pauses After | User Reviews | User Can Edit |
|---|---|---|---|---|
| 1 | Data Parse Confirmation | `layer1` | Source type, language detection, sheet list, first N rows preview | Select sheet, change header row, change language |
| 2 | Content Extraction Confirmation | `layer2_extract` | **Structured, grouped content elements** (facts/data/opinions/conclusions with confidence scores) | Delete/modify/add elements |
| 3 | Narrative Structure Confirmation | `layer2_narrative` | Core arguments, section roles (opening/problem/analysis/solution/summary), transitions | Edit arguments, reorder sections |
| 4 | Page Structure Confirmation | `layer3` | Per-slide takeaway + slide_type + estimated elements | Edit takeaway, merge/split pages, reorder |

**After checkpoint 4**: Layer 4 + 5 + 6 run consecutively without pausing (execution layers, all decisions already confirmed).

```
PAUSE_AFTER_STAGES = {"layer1", "layer2_extract", "layer2_narrative", "layer3"}
```

**No skip button**. All 4 checkpoints are mandatory. This is a professional PPT system, not a speed tool.

### Checkpoint 2 Display Format

Content extraction results must be displayed as **LLM-organized, grouped output** - NOT raw text. Elements are deduplicated, contextualized, and grouped by type:

```
Content Extraction Results (23 elements)

  Data (8)
  - 2024 revenue grew 32% YoY to 1.56B           [0.95]
  - East China accounts for 47% of total revenue  [0.92]
  ...

  Facts (7)
  - Company completed org restructuring in 2023   [0.90]
  ...

  Conclusions (4)
  - Digital transformation is the core driver      [0.93]
  ...

  Opinions (4)
  - Recommend increasing East China investment     [0.85]
  ...
```

Each element is an independent argumentative unit with complete sentence meaning, not a raw excerpt.

### Data Model

The `SlideSpec` object is the core data structure that flows through the pipeline:

```python
class SlideSpec:
    # Metadata
    slide_id: str
    slide_type: str  # "title", "content", "data", "diagram", "summary"

    # Content layer (filled by Layer 3)
    takeaway_message: str  # Core argument of this slide
    narrative_arc: str  # Role in overall story
    sections: List[Section]

    # Data layer (filled by Layer 2)
    data_references: List[DataRef]
    key_insights: List[str]

    # Visual layer (filled by Layer 4)
    layout_template: str
    visual_style: StyleSpec
    language: str  # "zh" or "en" - affects font sizing

    # Chart layer (filled by Layer 5)
    charts: List[ChartSpec]

    # Layout layer (filled by Layer 6)
    layout_coordinates: Dict
```

## Technology Stack

- **Frontend**: Streamlit (transitional; will migrate to React)
- **Backend**: FastAPI (monolithic, not microservices)
- **Storage**: Local filesystem + SQLite (with abstraction layer for future S3/PostgreSQL migration)
- **LLM**: Multi-provider domestic models (Zhipu GLM + DeepSeek + Alibaba Tongyi Qwen)
- **PPT Generation**: python-pptx (native chart objects, shape+connector for diagrams)
- **Real-time Communication**: Polling via `time.sleep+st.rerun` (SSE deferred to React frontend)
- **Encryption**: Fernet + PBKDF2HMAC per-user key derivation
- **Deployment**: Docker + docker-compose

## Multi-Provider LLM Architecture

### Provider Classification by Capability

All providers are domestic (China) models for latency and compliance reasons.

| Capability Domain | Provider | Model | Used In | Rationale |
|---|---|---|---|---|
| Chinese comprehension / extraction | Zhipu (智谱) | GLM-4-Plus / GLM-4-Flash | layer2_extract | Strong Chinese understanding, cost-effective for extraction tasks |
| Narrative reasoning / structure planning | DeepSeek (深度求索) | DeepSeek-R1 | layer2_narrative, layer3 | Strongest reasoning chain among domestic models, excellent structured thinking |
| Data analysis / chart narrative | Alibaba Tongyi (阿里通义) | Qwen-Max | layer5 (chart so-what) | Stable data reasoning, reliable structured JSON output |

### LLM Call Points in Pipeline

```
layer1           -- Rule engine, NO LLM
layer2_extract   -- Zhipu GLM-4-Plus      (information extraction & classification)
layer2_narrative -- DeepSeek-R1            (narrative arrangement, quality-critical)
layer3           -- DeepSeek-R1            (takeaway planning, quality-critical)
layer4           -- Rule engine, NO LLM
layer5           -- Qwen-Max               (chart so-what + data insights)
layer6           -- Rule engine, NO LLM
```

### Per-Stage Model Configuration

Each LLM-calling stage has its own model configuration. Users configure a global default and optionally override per-stage.

```python
class StageModelConfig:
    provider: str          # "zhipu", "deepseek", "tongyi"
    model: str             # "glm-4-plus", "deepseek-r1", "qwen-max"
    api_key: str           # Per-provider API key (encrypted in storage)
    base_url: Optional[str]
    temperature: float
    max_tokens: int

class PipelineModelConfig:
    layer2_extract: StageModelConfig
    layer2_narrative: StageModelConfig
    layer3: StageModelConfig
    layer5_chart_narrative: StageModelConfig
```

### LLM Client Architecture

```
llm_client/
  base.py              # LLMClient abstract base class: generate(prompt, ...)
  zhipu.py             # Zhipu GLM adapter (refactored from existing glm_client.py, uses zhipuai SDK)
  openai_compat.py     # OpenAI-compatible adapter (covers DeepSeek, Tongyi, Moonshot, etc.)
  factory.py           # get_client(provider, api_key, base_url) -> LLMClient
```

All providers implement the same `LLMClient.generate()` interface. Pipeline code only depends on the abstract interface, never on a specific provider.

DeepSeek and Tongyi both use the OpenAI-compatible protocol, so `openai_compat.py` covers both by switching `base_url`:
- DeepSeek: `https://api.deepseek.com/v1`
- Tongyi: `https://dashscope.aliyuncs.com/compatible-mode/v1`

Only Zhipu requires its own adapter (`zhipu.py`) due to its proprietary SDK.

## API Key Encryption

### Scheme: System Master Key + Per-User Derived Keys

Designed for future multi-user support.

```
Environment:
  MASTER_ENCRYPTION_KEY=<Fernet key>     # Generated once at deployment

SQLite: api_keys table
  user_id | provider | encrypted_key | created_at

Encryption flow:
  derived_key = PBKDF2HMAC(master_key, salt=user_id)
  encrypted   = Fernet(derived_key).encrypt(api_key_bytes)

Decryption flow:
  derived_key = PBKDF2HMAC(master_key, salt=user_id)
  api_key     = Fernet(derived_key).decrypt(encrypted_bytes)
```

- Single-user phase: `user_id` = `"default"`
- Multi-user phase: Each user's keys encrypted with their own derived key
- Only one env var to manage: `MASTER_ENCRYPTION_KEY`

## Project Structure

```
PPTagent/
  api/                         # FastAPI backend
    main.py                    # API endpoints + pipeline dispatch
    pipeline_controller.py     # Stage-level controller with 4 checkpoints
  pipeline/                    # Core 6-layer pipeline engine
    layer1_input/              # Input parsing (DOCX/XLSX/CSV/PPTX/TXT/MD)
    layer2_content/            # Content extraction + narrative building (LLM)
    layer3_structure/          # Slide structure planning
    layer4_visual/             # Visual design (layout templates + themes)
    layer5_chart/              # Chart specification generation
    layer6_output/             # Layout engine + PPT builder
    skills/                    # Rendering Skills (Prompt + DesignTokens + Render)
      __init__.py              # SkillRegistry (singleton dict-based registry)
      base.py                  # RenderingSkill ABC + SkillDescriptor
      _utils.py                # Shared rendering utils (color, font, textbox)
      visual_blocks/           # 6 VB Skills (kpi_cards, step_cards, etc.)
      charts/                  # 8 Chart Skills (template method pattern, 1 file)
      diagrams/                # 4 Diagram Skills (process_flow, architecture, etc.)
  models/                      # Data models
    slide_spec.py              # SlideSpec, PresentationSpec, etc.
    model_config.py            # StageModelConfig, PipelineModelConfig
  llm_client/                  # Multi-provider LLM client
    base.py                    # Abstract base class
    zhipu.py                   # Zhipu GLM adapter (proprietary SDK)
    openai_compat.py           # OpenAI-compatible adapter (DeepSeek, Tongyi, etc.)
    factory.py                 # Provider factory
  templates/                   # Layout skeletons + visual themes
  storage/                     # Persistence layer
    task_store.py              # SQLite: tasks + pipeline_stages + settings + api_keys
    encryption.py              # Fernet + PBKDF2HMAC key management
  frontend/                    # Streamlit application (transitional)
  output/                      # Generated PPT files
  docker-compose.yml           # Production deployment
  docker-compose.dev.yml       # Development with hot reload
```

## Key Technical Decisions

### Skill Architecture
**Skill = Prompt 指导 + 设计参数 + 渲染规则**（三位一体的设计知识封装单元）

Each Skill implements `RenderingSkill` ABC with three methods:
- `prompt_fragment()`: Design guidance injected into LLM prompts for content generation
- `design_tokens()`: Design parameters (colors from theme, font sizes, spacing) — no hardcoded values
- `render()`: python-pptx rendering logic with quality improvements

`SkillRegistry` provides centralized registration and lookup. `ppt_builder.py` and `diagram_renderer.py` dispatch through the registry first, falling back to original methods.

`content_filler.py` dynamically assembles LLM prompts from SkillRegistry — only including guidance for types present in the current batch (attention focus).

**Adding a new visual type** (e.g., radar chart):
1. Create `pipeline/skills/charts/radar.py` with `RadarChartSkill`
2. Register it in `charts/__init__.py`
3. Add enum value to `slide_spec.py`
4. Done — prompt, design tokens, and rendering all self-contained

### LLM Integration
- **Multi-provider domestic models**: Zhipu GLM (extraction), DeepSeek (reasoning), Tongyi Qwen (data analysis)
- **Per-stage configuration**: Each LLM-calling stage can use a different provider/model
- Wrap all calls in unified `LLMClient` interface with retry, timeout, and cost tracking
- Token estimation and caching to control costs
- OpenAI-compatible interface covers DeepSeek, Tongyi, and other domestic providers via `base_url` switch
- Only Zhipu requires a dedicated adapter (proprietary SDK); all others use `openai_compat.py`

### Chart Generation
- **Data charts**: Use python-pptx native chart objects (vectorized, editable)
- **Topology/architecture diagrams**: Use shape + connector primitives in PPT
- Avoid matplotlib for data charts (static images blur when scaled)
- Automatically generate chart narratives with "so what" insights
- Chart annotations positioned by rule engine (highest/lowest bar, trend inflection points)

### Layout System
- **15-20 predefined layout skeletons** with parametric adjustments
- Each skeleton defines "slot regions" with position and proportion
- Adjust font size, line spacing, margins based on content density
- Support Chinese and English with different default parameters (Chinese needs 1-2pt larger fonts)
- No constraint solver; predefined templates + parametric tuning covers all cases

### Template System
**Two-level classification:**
1. **Content structure patterns** (12 core + 6 extended): argument-evidence, comparison, timeline, matrix, process-flow, data-dashboard, etc.
2. **Visual themes** (4-5 initially): consulting-formal, tech-modern, business-minimalist, finance-stable, creative-vibrant

### Input Formats
Supported: `.txt`, `.docx`, `.xlsx`, `.csv`, `.pptx`, `.md`

Markdown parsing extracts heading hierarchy, lists, tables, and code blocks. Markdown tables are converted to structured `TableData`. Code blocks are preserved with markers for Layer 2 to recognize technical content.

### Storage
- **SQLite** with tables: `tasks`, `pipeline_stages`, `settings`, `api_keys`
- `TaskStore` class provides abstraction layer
- `pipeline_stages.result` stores JSON-serialized stage outputs for editing and re-running
- `reset_stages_from()` clears a stage and all subsequent stages when user edits
- API keys encrypted with Fernet + PBKDF2HMAC (see encryption section)
- Easy migration to S3/PostgreSQL in future

### Frontend Strategy
- **Current**: Streamlit as transitional diagnostic interface
- **Future**: React SPA consuming the same FastAPI backend
- Streamlit investment is minimal: functional but not polished
- All business logic lives in backend API; frontend is a thin presentation layer
- Backend is already API-ready: all operations exposed as REST endpoints

## Docker Configuration

### Container Architecture

```
docker-compose.yml structure:
  backend (FastAPI)
    Image: Python 3.11+
    Volumes: ./api:/app/api, ./storage:/app/storage
    Environment: MASTER_ENCRYPTION_KEY, DATABASE_URL
    Ports: 8000 (internal)

  frontend (Streamlit)
    Image: Python 3.11+
    Volumes: ./frontend:/app/frontend
    Environment: BACKEND_URL=http://backend:8000
    Ports: 8501 (internal)

  nginx (optional, production)
    Ports: 80:80, 443:443
    Proxies: /api/* -> backend:8000, /* -> frontend:8501
```

### Docker Commands
```bash
# Production deployment
docker-compose up -d

# Development with hot reload
docker-compose -f docker-compose.dev.yml up

# View logs
docker-compose logs -f [service_name]

# Stop services
docker-compose down
```

## Development Workflow

### IMPORTANT: Docker-First Development (MUST follow)

**All services MUST run in Docker containers. Never run backend/frontend locally.**

- Backend (FastAPI), Frontend (React), and Database (PostgreSQL) all run in Docker
- Code changes require rebuilding Docker images: `docker-compose build [service]`
- New Python dependencies must be added to `requirements.txt` and containers rebuilt
- Database runs in its own container (ppt-agent-db-dev)

```bash
# Build and start all services (after code changes)
docker-compose -f docker-compose.dev.yml up --build

# Rebuild only backend (after adding dependencies or code changes)
docker-compose -f docker-compose.dev.yml up --build -d backend

# View logs
docker-compose logs -f backend

# Stop all services
docker-compose -f docker-compose.dev.yml down

# Execute commands inside running container
docker-compose exec backend python3 -c "..."
```

### Key Development Principles
1. **Docker-first**: All services run in Docker, never locally
2. **Quality over speed**: 3-10 minute generation time is acceptable, no shortcuts
3. **2 mandatory checkpoints**: outline and content are user review points
4. **Incremental SlideSpec**: Each layer fills its designated fields only
5. **Backend-first**: All logic in API; frontend is a thin shell
6. **Multi-provider LLM**: Each stage uses the best model for its task
7. **Encrypted secrets**: API keys never stored in plaintext
8. **New dependencies**: Add to requirements.txt → rebuild Docker image

### Brand Customization
Support enterprise brand packages (logo + primary/secondary colors + fonts) that override default visual themes. Logo placement is predefined in layout skeletons.

## Architecture Patterns

### Dependency Management
Use a dependency graph to track which slides depend on others. When users modify a takeaway, only mark that slide and its direct dependents (e.g., related charts) as dirty for regeneration.

### Error Handling
Each layer should:
- Validate inputs before processing
- Provide meaningful error messages at layer boundaries
- Support partial regeneration when only some slides are dirty

### Testing Strategy
- Unit tests for individual layers (especially Layout Engine coordinate calculations)
- Integration tests for full pipeline with sample inputs
- Visual regression tests for generated PPT outputs
