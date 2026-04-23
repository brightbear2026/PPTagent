# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

PPT Agent generates consulting-grade `.pptx` presentations from text/documents. The system emphasizes high information density, professional visual design, and transparent human control at 2 mandatory checkpoints.

**Core Goals:**
- Argument-driven outlines (Pyramid Principle), not document chapter mapping
- Support multiple input formats: DOCX / XLSX / CSV / PPTX / TXT / MD
- 2 mandatory user review checkpoints (outline + content)
- Quality over speed: 3-10 minute generation is acceptable

## Architecture

### 6-Agent Pipeline

```
parse → analyze → outline[checkpoint1] → content[checkpoint2] → design → render
```

Each agent's result is persisted in `pipeline_stages` PostgreSQL table. Users can edit any completed stage and re-run from that point via `POST /api/task/{id}/resume`.

| Stage | Agent | Description |
|-------|-------|-------------|
| `parse` | ParseAgent (code-only) | DOCX/XLSX/CSV/PPTX/TXT/MD → RawContent |
| `analyze` | AnalyzeAgent (LLM) | Document strategy + audience analysis + **chunk generation** |
| `outline` | **PlanAgent** (LLM) | Pyramid Principle → DeckPlan (SCQA + argument slides) |
| `content` | ContentAgent (LLM, per-slide parallel) | Each slide's text blocks + chart/diagram specs |
| `design` | DesignAgent (code + optional LLM) | Layout templates + visual themes + chart conversion |
| `render` | RenderAgent (code-only) | python-pptx → `.pptx` file |

### 2 Mandatory Checkpoints

```
CHECKPOINT_AGENTS = {"outline", "content"}
```

| # | Checkpoint | After Stage | User Reviews | User Can Edit |
|---|---|---|---|---|
| 1 | Outline Confirmation | `outline` | SCQA structure, all slides with takeaway messages, narrative flow | Edit any field, reorder, delete pages |
| 2 | Content Confirmation | `content` | Per-slide text blocks, chart data, diagram specs | Edit text, modify chart data, rerun single page |

After checkpoint 2: design → render run automatically without pausing.

### PlanAgent — Pyramid Principle Outline (key design)

**Why PlanAgent exists**: The old OutlineAgent used `recommended_structure` (a natural-language string like "开篇→问题→分析→方案→行动") split by "→" to allocate pages uniformly. This produced chapter-mapping outlines ("materials decomposition") instead of argument sequences.

**PlanAgent approach**:
- User's `scenario` choice (季度汇报/战略提案/竞标pitch etc.) hard-maps to a narrative framework (SCR/SCQA/AIDA), not LLM-inferred
- System prompt emphasizes: "PPT is an argument, not a table of contents; each slide's takeaway_message must be a complete sentence with a verb"
- Outputs SCQA structure + slides array where each slide has a clear claim (action title)
- Rule-based verification + 1 LLM fix pass for quality

**Output format** (compatible with existing ContentAgent):
```json
{
  "narrative_logic": "SCQA框架：...",
  "scqa": {"situation": "...", "complication": "...", "question": "...", "answer": "..."},
  "root_claim": "顶层结论",
  "items": [OutlineItem dicts...],
  "data_gap_suggestions": []
}
```

### Data Model

`SlideSpec` is the core object flowing through design → render. Key fields set by each layer:

| Layer | Fields Set |
|-------|-----------|
| parse | RawContent (source_pages, tables, raw_text) |
| analyze | StrategyInsight, chunks (for PlanAgent), derived_metrics |
| outline | OutlineItem list (slide_type, takeaway_message, supporting_hint, narrative_arc) |
| content | SlideContent (text_blocks, chart_suggestion, diagram_spec, visual_block) |
| design | SlideSpec fully populated (layout_template, visual_theme, charts, diagrams) |
| render | .pptx file |

## Technology Stack

| Component | Technology |
|-----------|-----------|
| Backend | FastAPI + Uvicorn |
| Frontend | React 18 + TypeScript + Vite + Ant Design |
| Database | PostgreSQL (Alembic migrations) |
| LLM | Any OpenAI-compatible API (SiliconFlow / DeepSeek / Tongyi / Zhipu etc.) |
| PPT Generation | python-pptx (native vector chart objects) |
| Encryption | Fernet + PBKDF2HMAC per-user key derivation |
| Deployment | Docker + docker-compose |

## LLM Configuration

All providers use OpenAI-compatible protocol via `base_url` switch. Per-stage model config allows different models per pipeline stage.

### Provider Config in `models/model_config.py`

```python
class StageModelConfig:
    provider: str      # "openai_compat" | "zhipu"
    model: str
    api_key: str       # encrypted in DB; plaintext in memory only
    base_url: str
    temperature: float
    max_tokens: int

class PipelineModelConfig:
    # Per-stage configs; get_stage_config(stage) returns the right one
    analyze: StageModelConfig
    outline: StageModelConfig
    content: StageModelConfig
    design: StageModelConfig
```

### LLM Client Architecture

```
llm_client/
  base.py          # LLMClient ABC: chat(messages, tools, ...) -> ChatResponse
  openai_compat.py # OpenAI-compatible adapter (covers DeepSeek, Tongyi, SiliconFlow, etc.)
  glm_client.py    # Zhipu GLM proprietary SDK adapter
  factory.py       # get_client(provider, ...) -> LLMClient
```

Only Zhipu requires its own adapter (proprietary SDK). All others use `openai_compat.py` with different `base_url`.

## API Key Encryption

```
MASTER_ENCRYPTION_KEY env var (Fernet key, set once at deployment)
  └─ per-user derived key = PBKDF2HMAC(master, salt=user_id)
       └─ encrypted_api_key = Fernet(derived).encrypt(api_key_bytes)
```

Stored in `api_keys` table. Single-user: `user_id = "default"`.

## Project Structure

```
PPTagent/
  api/
    main.py                  # FastAPI endpoints + task dispatch
  pipeline/
    agents/
      parse_agent.py         # Code-only: multi-format document parser
      analyze_agent.py       # LLM: document strategy + _chunk_document()
      plan_agent.py          # LLM: Pyramid Principle outline (SCQA + slides)
      content_agent.py       # LLM: per-slide parallel content generation
      design_agent.py        # Code + optional LLM: layout + visual design
      render_agent.py        # Code-only: python-pptx builder
      base.py                # ReActAgent / CodeAgent base classes
    layer1_input/            # Format-specific parsers (DOCX/XLSX/CSV/MD/TXT/PPTX)
    layer4_visual/           # VisualDesigner (layout templates + themes)
    layer5_chart/            # ChartGenerator (chart spec → ChartSpec)
    layer6_output/           # PPT builder + diagram renderer
    skills/                  # Rendering skills registry (charts/diagrams/visual_blocks)
    orchestrator.py          # Stage-by-stage execution + checkpoint management
  models/
    slide_spec.py            # All data models (SlideSpec, OutlineItem, SCQA, etc.)
    model_config.py          # PipelineModelConfig, StageModelConfig
  llm_client/                # Multi-provider LLM client
  storage/
    task_store.py            # PostgreSQL: tasks + pipeline_stages + settings + api_keys
    encryption.py            # Fernet + PBKDF2HMAC key management
  migrations/                # Alembic database migrations
  frontend-react/            # React 18 wizard UI
    src/
      pages/WizardPage.tsx   # Main flow control + SSE progress
      components/wizard/     # Step1Upload, Step2Outline, Step3Content, Step4Download
      hooks/useSSE.ts        # Real-time progress subscription
  templates/                 # Layout skeletons + visual themes JSON
  docker-compose.yml
  docker-compose.dev.yml
```

## Development Workflow

### IMPORTANT: Docker-First

All services run in Docker. Never run backend/frontend locally.

```bash
# Build and start all services
docker-compose -f docker-compose.dev.yml up --build

# Rebuild only backend (after code changes)
docker-compose -f docker-compose.dev.yml up --build -d backend

# View logs
docker-compose logs -f backend

# Run inside container
docker-compose exec backend python3 -c "..."
```

### Adding New Features

**New visual skill** (chart/diagram/visual block):
1. Create `pipeline/skills/{category}/new_skill.py` implementing `RenderingSkill`
2. Register in `pipeline/skills/{category}/__init__.py`
3. Add enum value to `models/slide_spec.py`

**New LLM provider**:
1. If OpenAI-compatible: just configure `base_url` in settings UI
2. If proprietary SDK: create `llm_client/new_provider.py` adapter
3. Register in `llm_client/factory.py`

### Key Principles

1. **Docker-first**: Always rebuild container after code changes
2. **PlanAgent = Pyramid Principle**: Outline is an argument sequence, not chapter mapping
3. **Per-slide parallel**: ContentAgent runs MAX_CONCURRENT=4 slides simultaneously  
4. **OutlineItem → ContentAgent compatibility**: PlanAgent output uses `items` key; ContentAgent reads `outline.get("items", outline.get("slides", []))`
5. **narrative_arc values** must match `NarrativeRole` enum: opening / context / evidence / analysis / solution / recommendation / closing
6. **API keys**: Never stored in plaintext; always encrypt with `storage/encryption.py`
7. **New Python deps**: Add to `requirements.txt` → rebuild Docker image

## Scenario → Framework Mapping (PlanAgent)

User's Step1 `scenario` selection hard-maps to narrative framework:

| scenario | Framework | narrative_arc hint |
|----------|-----------|-------------------|
| 季度汇报 | SCR | situation→complication→resolution |
| 战略提案 | SCQA | situation→complication→question→answer |
| 竞标pitch | AIDA | attention→interest→desire→action |
| 内部分析 | Issue Tree | MECE decomposition |
| 培训材料 | Explanation | objective→gap→solution→evaluation |
| 项目汇报 | STAR | situation→task→action→result |
| 产品发布 | Problem-Solution | problem tree + solution tree |
| (auto) | LLM decides | scr / problem_solution / explanation |

## Known Issues & Roadmap

### P1 (next iteration)
- SSE: currently 0.5s polling; should use asyncio.Queue event-driven push
- Step1 sub-progress not visible during parse+analyze (5%→30% is a black box)
- `_find_chart_table`: only injects top-2 tables; could use BM25 row-level filtering for large tables

### P2 (technical debt)
- `analyze_agent.py:_analyze_table_code` references `MetricType.GROWTH_RATE` which doesn't exist (should be `YOY_GROWTH`); currently caught by try/except so non-fatal
- `SupplementalData.micro_analysis` is a dead column in the DB schema
- stagger/sleep patterns in old code paths should be replaced with tenacity exponential backoff
