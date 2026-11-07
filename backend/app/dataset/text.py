"""Text assembly with exact character-offset tracking for facts and entity mentions."""

from __future__ import annotations

import random
import re
from dataclasses import dataclass, field

from backend.app.dataset.canonical import Canonical, Deployment

PLACEHOLDER = re.compile(r"\{(svc|dpl|ext):([A-Za-z0-9\-]+)(\|name)?\}")
FACT_MARKER = re.compile(r"\[\[(F-[A-Za-z0-9\-]+)\|(.*?)\]\]", re.DOTALL)


@dataclass(frozen=True)
class Span:
    start: int
    end: int


@dataclass(frozen=True)
class FactMention:
    fact_id: str
    start: int
    end: int
    stance: str  # supports | preliminary


@dataclass(frozen=True)
class EntityMention:
    entity_id: str
    start: int
    end: int
    surface: str


@dataclass
class TextBuilder:
    """Append-only text buffer; every fragment can carry fact ids that cover its span."""

    renderer: Renderer
    _parts: list[str] = field(default_factory=list)
    _length: int = 0
    facts: list[FactMention] = field(default_factory=list)
    entities: list[EntityMention] = field(default_factory=list)

    def raw(self, text: str) -> Span:
        start = self._length
        self._parts.append(text)
        self._length += len(text)
        return Span(start, self._length)

    def add(
        self, template: str, facts: tuple[str, ...] | list[str] = (), stance: str = "supports"
    ) -> Span:
        """Render placeholders in `template`, append it and attach facts to the whole span."""
        text, mentions = self.renderer.render(template)
        span = self.raw(text)
        for m in mentions:
            self.entities.append(
                EntityMention(m.entity_id, span.start + m.start, span.start + m.end, m.surface)
            )
        for fact_id in facts:
            self.facts.append(FactMention(fact_id, span.start, span.end, stance))
        return span

    def line(
        self, template: str = "", facts: tuple[str, ...] | list[str] = (), stance: str = "supports"
    ) -> Span:
        span = self.add(template, facts, stance)
        self.raw("\n")
        return span

    def authored(self, body: str) -> None:
        """Append hand-written markdown, converting [[F-ID|text]] markers into fact spans."""
        cursor = 0
        for match in FACT_MARKER.finditer(body):
            self.add(body[cursor : match.start()])
            self.add(match.group(2), facts=(match.group(1),))
            cursor = match.end()
        self.add(body[cursor:])

    @property
    def text(self) -> str:
        return "".join(self._parts)


class Renderer:
    """Renders {svc:}/{dpl:}/{ext:} placeholders with deterministic per-document aliasing."""

    def __init__(self, canonical: Canonical, seed: str) -> None:
        self.c = canonical
        self.rng = random.Random(seed)

    def service_surface(self, slug: str, force_name: bool = False) -> str:
        svc = self.c.services[slug]
        if force_name:
            return svc.name
        roll = self.rng.random()
        if roll < 0.5:
            return svc.name
        if roll < 0.75:
            return svc.slug
        return self.rng.choice(svc.surface_forms())

    def deployment_surface(self, dpl: Deployment) -> str:
        svc = self.service_surface(dpl.service)
        if dpl.kind == "rollback":
            return f"the rollback of {svc} to {dpl.version}"
        if dpl.kind == "config_change":
            return f"the {svc} config change {dpl.version}"
        if dpl.kind == "infra_upgrade":
            return f"the {svc} {dpl.version} upgrade"
        bare = dpl.version.removeprefix("v")
        style = self.rng.randrange(4)
        if style == 0:
            return f"{svc} {dpl.version}"
        if style == 1:
            return f"the {svc} {dpl.version} release"
        if style == 2:
            return f"{svc} release {bare}"
        return f"version {bare} of {svc}"

    def render(self, template: str) -> tuple[str, list[EntityMention]]:
        out: list[str] = []
        mentions: list[EntityMention] = []
        cursor = 0
        length = 0
        for match in PLACEHOLDER.finditer(template):
            literal = template[cursor : match.start()]
            out.append(literal)
            length += len(literal)
            kind, ref, force = match.group(1), match.group(2), bool(match.group(3))
            if kind == "svc":
                surface = self.service_surface(ref, force)
                entity_id = self.c.services[ref].id
            elif kind == "dpl":
                dpl = self.c.deployments[ref]
                surface = self.deployment_surface(dpl)
                entity_id = dpl.id
            else:
                surface = self.c.externals[ref].name
                entity_id = ref
            out.append(surface)
            mentions.append(EntityMention(entity_id, length, length + len(surface), surface))
            length += len(surface)
            cursor = match.end()
        out.append(template[cursor:])
        return "".join(out), mentions
