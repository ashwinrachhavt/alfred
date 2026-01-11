from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Optional

from alfred.schemas.system_design import ExcalidrawData


@dataclass(frozen=True)
class DiagramNode:
    element_id: str
    label: str
    export_id: str


@dataclass(frozen=True)
class DiagramEdge:
    source_id: str
    target_id: str
    label: Optional[str] = None
    directed: bool = True


def _iter_elements(diagram: ExcalidrawData) -> Iterable[dict[str, Any]]:
    for el in diagram.elements or []:
        if isinstance(el, dict):
            yield el


def _is_deleted(el: dict[str, Any]) -> bool:
    return bool(el.get("isDeleted"))


def _is_edge(el: dict[str, Any]) -> bool:
    return el.get("type") in {"arrow", "line"}


def _is_text(el: dict[str, Any]) -> bool:
    return el.get("type") == "text"


def _is_node(el: dict[str, Any]) -> bool:
    if _is_deleted(el):
        return False
    t = el.get("type")
    if not isinstance(t, str):
        return False
    if t in {"arrow", "line", "text", "image", "frame"}:
        return False
    return bool(el.get("id"))


def _get_label_from_element(el: dict[str, Any]) -> Optional[str]:
    label = el.get("label")
    if isinstance(label, dict):
        text = label.get("text")
        if isinstance(text, str) and text.strip():
            return text.strip()
    text = el.get("text")
    if isinstance(text, str) and text.strip():
        return text.strip()
    return None


def _index_text_by_container(elements: Iterable[dict[str, Any]]) -> dict[str, str]:
    out: dict[str, str] = {}
    for el in elements:
        if _is_deleted(el) or not _is_text(el):
            continue
        container_id = el.get("containerId")
        text = el.get("text")
        if not isinstance(container_id, str) or not isinstance(text, str):
            continue
        normalized = text.strip()
        if not normalized:
            continue
        out.setdefault(container_id, normalized)
    return out


def _extract_nodes(diagram: ExcalidrawData) -> dict[str, DiagramNode]:
    elements = list(_iter_elements(diagram))
    container_text = _index_text_by_container(elements)

    nodes: list[DiagramNode] = []
    for el in elements:
        if not _is_node(el):
            continue
        element_id = el.get("id")
        if not isinstance(element_id, str) or not element_id:
            continue
        label = _get_label_from_element(el) or container_text.get(element_id) or "Component"
        nodes.append(DiagramNode(element_id=element_id, label=label, export_id=""))

    # Deterministic IDs (N1, N2, ...) to avoid leaking internal Excalidraw IDs.
    nodes_sorted = sorted(nodes, key=lambda n: (n.label.lower(), n.element_id))
    indexed: dict[str, DiagramNode] = {}
    for idx, node in enumerate(nodes_sorted, start=1):
        indexed[node.element_id] = DiagramNode(
            element_id=node.element_id, label=node.label, export_id=f"N{idx}"
        )
    return indexed


def _binding_element_id(binding: Any) -> Optional[str]:
    if not isinstance(binding, dict):
        return None
    element_id = binding.get("elementId")
    if isinstance(element_id, str) and element_id:
        return element_id
    return None


def _extract_edges(diagram: ExcalidrawData, nodes: dict[str, DiagramNode]) -> list[DiagramEdge]:
    elements = list(_iter_elements(diagram))
    container_text = _index_text_by_container(elements)

    edges: list[DiagramEdge] = []
    for el in elements:
        if _is_deleted(el) or not _is_edge(el):
            continue
        element_id = el.get("id")
        if not isinstance(element_id, str) or not element_id:
            continue
        start_id = _binding_element_id(el.get("startBinding"))
        end_id = _binding_element_id(el.get("endBinding"))
        if not start_id or not end_id:
            continue
        if start_id not in nodes or end_id not in nodes:
            continue
        label = container_text.get(element_id)
        edges.append(
            DiagramEdge(
                source_id=nodes[start_id].export_id,
                target_id=nodes[end_id].export_id,
                label=label,
                directed=el.get("type") == "arrow",
            )
        )

    unique: dict[tuple[str, str, Optional[str], bool], DiagramEdge] = {}
    for edge in edges:
        unique[(edge.source_id, edge.target_id, edge.label, edge.directed)] = edge
    return sorted(unique.values(), key=lambda e: (e.source_id, e.target_id, e.label or ""))


def _escape_mermaid_label(label: str) -> str:
    return label.replace('"', '\\"').replace("\n", " ").strip()


def _escape_plantuml_label(label: str) -> str:
    return label.replace('"', '""').replace("\n", " ").strip()


def diagram_to_mermaid(diagram: ExcalidrawData, *, direction: str = "LR") -> str:
    """Convert an Excalidraw diagram into a Mermaid flowchart.

    This is a best-effort export based on bound shapes + arrows.
    """

    nodes = _extract_nodes(diagram)
    edges = _extract_edges(diagram, nodes)

    dir_token = direction.strip().upper() if direction else "LR"
    if dir_token not in {"LR", "RL", "TB", "BT"}:
        dir_token = "LR"

    lines: list[str] = [f"flowchart {dir_token}"]
    for node in sorted(nodes.values(), key=lambda n: int(n.export_id[1:])):
        lines.append(f'    {node.export_id}["{_escape_mermaid_label(node.label)}"]')

    for edge in edges:
        arrow = "-->" if edge.directed else "---"
        if edge.label:
            label = edge.label.replace("|", "/")
            lines.append(
                f"    {edge.source_id} {arrow}|{_escape_mermaid_label(label)}| {edge.target_id}"
            )
        else:
            lines.append(f"    {edge.source_id} {arrow} {edge.target_id}")

    return "\n".join(lines).rstrip() + "\n"


def diagram_to_plantuml(diagram: ExcalidrawData) -> str:
    """Convert an Excalidraw diagram into a PlantUML component diagram."""

    nodes = _extract_nodes(diagram)
    edges = _extract_edges(diagram, nodes)

    lines: list[str] = ["@startuml", "left to right direction"]
    for node in sorted(nodes.values(), key=lambda n: int(n.export_id[1:])):
        lines.append(f'component "{_escape_plantuml_label(node.label)}" as {node.export_id}')

    for edge in edges:
        arrow = "-->" if edge.directed else "--"
        if edge.label:
            lines.append(
                f"{edge.source_id} {arrow} {edge.target_id} : {_escape_plantuml_label(edge.label)}"
            )
        else:
            lines.append(f"{edge.source_id} {arrow} {edge.target_id}")

    lines.append("@enduml")
    return "\n".join(lines).rstrip() + "\n"

