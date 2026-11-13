"""Пакет «Выгрузка в документ»: превращает граф идеи в читаемый текст. Работает кодом, без модели."""

from __future__ import annotations

import time
from pathlib import Path

from idea_graph_core import DETAIL, HUMAN, PROPOSED, ROOT_KIND, author_name

__version__ = "0.1.0"

FILE_NAME = "idea.md"
SERVICE = ("замечание", "открытый вопрос")


def _flags(card: dict) -> str:
    marks = []
    if card["status"] == PROPOSED:
        marks.append("предложена, не принята")
    decision = card.get("decision")
    if isinstance(decision, dict):
        if decision.get("assumption"):
            marks.append("допущение")
        if decision.get("by") and decision["by"] != HUMAN:
            marks.append("решил агент")
        if decision.get("disputed"):
            marks.append("после спора")
    return f" _({'; '.join(marks)})_" if marks else ""


def _one_line(text: str) -> str:
    return " ".join((text or "").split())


def _chosen(decision: dict) -> str:
    chosen = decision.get("chosen") or {}
    if chosen.get("type") == "rejected":
        return "все варианты отклонены"
    return str(chosen.get("value", ""))


def render(store) -> str:
    """Собрать документ из графа."""
    cards, edges = store.cards, list(store.edges.values())
    root = cards[store.root_id]
    children: dict[str, list[str]] = {}
    for edge in sorted(edges, key=lambda e: int(e["id"][1:])):
        if edge["kind"] == DETAIL:
            children.setdefault(edge["to"], []).append(edge["from"])
    shown: set[str] = {root["id"]}
    out = [f"# {root['title']}", ""]
    if root.get("body"):
        out += [root["body"].strip(), ""]
    out += [f"> Выгружено из графа идеи: ревизия {store.revision}, {time.strftime('%d.%m.%Y %H:%M')}.", ""]

    def bullet(card_id: str, depth: int) -> None:
        card = cards[card_id]
        if card_id in shown:
            out.append("  " * depth + f"- см. выше: {card['title']}")
            return
        shown.add(card_id)
        kind = "" if card["kind"] in ("решение", "ветка") else f"[{card['kind']}] "
        code = (card.get("attrs") or {}).get("formalize.code")
        body = _one_line(card.get("body"))
        out.append("  " * depth + f"- {kind}**{(code + ' ') if code else ''}{card['title']}**"
                   + (f" — {body}" if body else "") + _flags(card))
        for item in (card.get("attrs") or {}).get("formalize.acceptance") or []:
            out.append("  " * (depth + 1) + f"- ✓ {item}")
        for source in (card.get("attrs") or {}).get("research.sources") or []:
            out.append("  " * (depth + 1) + f"- источник: {source}")
        for child in children.get(card_id, []):
            if cards[child]["kind"] not in SERVICE:
                bullet(child, depth + 1)

    for top in children.get(root["id"], []):
        card = cards[top]
        if card["kind"] in SERVICE:
            continue
        shown.add(top)
        out += [f"## {card['title']}" + _flags(card), ""]
        if card.get("body"):
            out += [card["body"].strip(), ""]
        for child in children.get(top, []):
            if cards[child]["kind"] not in SERVICE:
                bullet(child, 0)
        out.append("")

    rest = [c for c in cards.values() if c["id"] not in shown and c["kind"] not in SERVICE]
    if rest:
        out += ["## Вне веток", ""]
        for card in rest:
            if card["id"] not in shown:
                bullet(card["id"], 0)
        out.append("")

    def section(title: str, items: list[str]) -> None:
        if items:
            out.extend([f"## {title}", "", *items, ""])

    section("Чего не делаем", [f"- **{c['title']}**" + (f" — {_one_line(c.get('body'))}" if c.get("body") else "")
                                for c in cards.values() if c["kind"] == "граница"])
    section("Допущения — решения, принятые без фактов",
            [f"- **{c['title']}** — {_one_line(c['decision'].get('rationale')) or 'обоснование не записано'}"
             for c in cards.values() if isinstance(c.get("decision"), dict) and c["decision"].get("assumption")])
    section("Открытые вопросы", [f"- {c['title']}" for c in cards.values() if c["kind"] == "открытый вопрос"])
    section("Замечания проверки",
            [f"- [{(c.get('attrs') or {}).get('check.level', 'заметка')}] **{c['title']}** — {_one_line(c.get('body'))}"
             for c in cards.values() if c["kind"] == "замечание"])

    decisions = [c for c in cards.values() if isinstance(c.get("decision"), dict) and c["decision"].get("chosen")]
    if decisions:
        out += ["## Журнал решений", "", "| Вопрос | Решение | Кто решил |", "|---|---|---|"]
        for card in sorted(decisions, key=lambda c: int(c["id"][1:])):
            decision = card["decision"]
            cell = lambda text: _one_line(str(text)).replace("|", "\\|")
            who = author_name(decision.get("by") or "") + (", допущение" if decision.get("assumption") else "")
            out.append(f"| {cell(decision.get('question') or card['title'])} | {cell(_chosen(decision))} | {cell(who)} |")
        out.append("")

    other = [e for e in edges if e["kind"] not in (DETAIL, "о карточке")]
    section("Связи между решениями",
            [f"- «{cards[e['from']]['title']}» — {e['kind']} → «{cards[e['to']]['title']}»" for e in other])
    return "\n".join(out).rstrip() + "\n"


def run(ctx) -> dict:
    text = render(ctx.store)
    path = Path(ctx.folder) / FILE_NAME
    path.write_text(text, encoding="utf-8")
    cards = ctx.store.cards
    pending = sum(1 for c in cards.values() if c["status"] == PROPOSED and c["kind"] not in SERVICE and c["kind"] != ROOT_KIND)
    summary = f"Документ {FILE_NAME} записан в папку идеи: карточек {len(cards)}"
    if pending:
        summary += f", из них не принято {pending}"
    return {"outcome": "готово", "summary": summary + ".", "files": [str(path)]}


def manifest() -> dict:
    return {
        "id": "export",
        "name": "Выгрузка в документ",
        "description": "Собирает из графа читаемый документ idea.md в папке идеи: ветки, решения, границы, "
                       "допущения, открытые вопросы и журнал решений.",
        "kind": "code",
        "order": 50,
        "reads": ["идея", "ветка", "решение", "граница", "требование", "факт"],
        "writes": [],
        "asks": False,
        "model_level": "не нужна",
        "outcomes": ["готово"],
        "run": run,
    }
