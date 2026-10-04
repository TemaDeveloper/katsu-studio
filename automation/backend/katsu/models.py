from __future__ import annotations
from typing import Literal
from pydantic import BaseModel, Field, ConfigDict, field_validator


class Model(BaseModel):
    model_config = ConfigDict(extra='forbid')


class StudioSettings(Model):
    target_seconds: int = Field(default=480, ge=60, le=1800)
    scene_count: int = Field(default=72, ge=4, le=120)
    text_model: str = Field(default='gpt-6-astra', min_length=1, max_length=100)
    image_model: str = Field(default='gpt-image-1.5', min_length=1, max_length=100)
    image_quality: Literal['low', 'medium', 'high'] = 'medium'
    voice_id: str = Field(default='', max_length=100)
    voice_name: str = Field(default='', max_length=150)
    voice_model: str = Field(default='eleven_multilingual_v2', min_length=1, max_length=100)
    voice_stability: float = Field(default=.5, ge=0, le=1)
    voice_similarity: float = Field(default=.75, ge=0, le=1)
    voice_speed: float = Field(default=1, ge=.7, le=1.2)
    words_per_minute: int = Field(default=145, ge=90, le=200)
    remove_pauses: bool = True
    pause_threshold_db: int = Field(default=-45, ge=-65, le=-25)
    minimum_pause_seconds: float = Field(default=.35, ge=.2, le=2)
    retained_pause_seconds: float = Field(default=.12, ge=.06, le=.3)
    image_concurrency: int = Field(default=2, ge=1, le=3)
    image_estimate_usd: float = Field(default=.10, gt=0, le=20)
    voice_per_1000_chars_usd: float = Field(default=.35, gt=0, le=20)
    text_request_estimate_usd: float = Field(default=.75, gt=0, le=20)
    budget_usd: float = Field(default=20, gt=0, le=500)


class ProjectCreate(Model):
    topic: str = Field(min_length=3, max_length=300)
    target_seconds: int = Field(default=480, ge=60, le=1800)
    scene_count: int = Field(default=72, ge=4, le=120)
    budget_usd: float | None = Field(default=None, gt=0, le=500)

    @field_validator('topic')
    @classmethod
    def meaningful(cls, value):
        if len(value.strip()) < 3:
            raise ValueError('Enter a topic with at least three characters.')
        return value.strip()


class Source(Model):
    title: str
    url: str
    evidence: str


class Claim(Model):
    claim: str
    source_urls: list[str]


class Script(Model):
    title: str
    narration: str
    sources: list[Source]
    claims: list[Claim]


class Scene(Model):
    id: int
    narration_start: int
    narration_end: int
    voiceover: str
    visual: str
    prompt: str
    label: str | None = None


class TimedWord(Model):
    word: str
    start: float
    end: float


class ThumbnailPlan(Model):
    headline: str = Field(min_length=3, max_length=60)
    visual: str = Field(min_length=3, max_length=3000)
    prompt: str = Field(min_length=3, max_length=6000)

    @field_validator('headline')
    @classmethod
    def brief_headline(cls, value):
        value = ' '.join(value.split()).upper()
        if not 2 <= len(value.split()) <= 6:
            raise ValueError('Use two to six words for the thumbnail headline.')
        return value


class Artifact(Model):
    kind: str
    path: str
    fingerprint: str
    metadata: dict = Field(default_factory=dict)


class ArtworkJob(Model):
    kind: str
    draft_id: str
    base_fingerprint: str
    instructions: str
    request_key: str
    image_model: str
    image_quality: Literal['low', 'medium', 'high']
    estimate: float
    previous_status: Literal['needs_attention', 'cancelled', 'completed']
    previous_stage: str
    previous_error: str | None = None
    previous_render_only: bool = False


class Project(Model):
    id: str
    topic: str
    title: str
    settings: StudioSettings
    status: Literal['queued', 'running', 'needs_attention', 'cancelled', 'completed'] = 'queued'
    stage: str = 'queued'
    completed_assets: int = 0
    total_assets: int = 0
    actual_seconds: float | None = None
    created_at: str
    updated_at: str
    artifacts: dict[str, Artifact] = Field(default_factory=dict)
    error: str | None = None
    cancel_requested: bool = False
    imported: bool = False
    estimated_committed_usd: float = 0
    thumbnail_revision: str = Field(default='', max_length=100)
    thumbnail_only: bool = False
    render_only: bool = False
    artwork_edit: ArtworkJob | None = None


class ArtworkEdit(Model):
    instructions: str = Field(min_length=3, max_length=4000)
    base_fingerprint: str = Field(min_length=1, max_length=128)

    @field_validator('instructions')
    @classmethod
    def meaningful_change(cls, value):
        if len(value.strip()) < 3:
            raise ValueError('Describe the change in at least three characters.')
        return value.strip()


class ArtworkApply(Model):
    draft_id: str = Field(min_length=1, max_length=128)


class ArtworkRestore(Model):
    fingerprint: str = Field(min_length=1, max_length=128)


class SceneEdit(Model):
    voiceover: str | None = Field(default=None, min_length=1, max_length=12000)
    visual: str | None = Field(default=None, min_length=1, max_length=3000)
