from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException

from mckainsey.config import Settings, get_settings
from mckainsey.models.phase_a import (
    KnowledgeProcessRequest,
    KnowledgeProcessResponse,
    PersonaFilterRequest,
    PersonaSampleResponse,
)
from mckainsey.services.lightrag_service import LightRAGService
from mckainsey.services.persona_sampler import PersonaSampler
from mckainsey.services.zep_logger import ZepEventLogger

router = APIRouter(prefix="/api/v1/phase-a", tags=["phase-a"])


@router.post("/personas/sample", response_model=PersonaSampleResponse)
def sample_personas(
    req: PersonaFilterRequest,
    settings: Settings = Depends(get_settings),
) -> PersonaSampleResponse:
    sampler = PersonaSampler(dataset_name=settings.nemotron_dataset, split=settings.nemotron_split)
    personas = sampler.sample(req)
    return PersonaSampleResponse(mode=req.mode, count=len(personas), personas=personas)


@router.post("/knowledge/process", response_model=KnowledgeProcessResponse)
async def process_knowledge(
    req: KnowledgeProcessRequest,
    settings: Settings = Depends(get_settings),
) -> KnowledgeProcessResponse:
    service = LightRAGService(settings)
    document_text = req.document_text
    source_path = req.source_path

    if req.use_default_demo_document and not document_text:
        default_path = _resolve_default_demo_path(settings.demo_default_policy_markdown)
        if not default_path.exists():
            raise HTTPException(
                status_code=404,
                detail=f"Default demo document not found: {settings.demo_default_policy_markdown}",
            )
        document_text = default_path.read_text(encoding="utf-8")
        source_path = str(default_path)

    if not document_text or len(document_text.strip()) < 20:
        raise HTTPException(
            status_code=422,
            detail="Provide document_text (min 20 chars) or set use_default_demo_document=true.",
        )

    try:
        result = await service.process_document(
            simulation_id=req.simulation_id,
            document_text=document_text,
            source_path=source_path,
            demographic_focus=req.demographic_focus,
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    zep = ZepEventLogger(settings.resolved_zep_key)
    zep.log_phase_a_event(
        simulation_id=req.simulation_id,
        payload=f"Processed policy doc {result['document_id']} via LightRAG.",
        source="phase-a-knowledge-process",
    )

    return KnowledgeProcessResponse(**result)


def _resolve_default_demo_path(config_path: str) -> Path:
    candidate = Path(config_path)
    if candidate.exists():
        return candidate

    # When API is launched from backend/, project-root paths are one level up.
    parent_candidate = Path("..") / config_path
    return parent_candidate
