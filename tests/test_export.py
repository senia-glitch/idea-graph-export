import pytest

from idea_graph_core import HUMAN, Store
from idea_graph_export import FILE_NAME, manifest, render, run


class Ctx:
    def __init__(self, store, folder):
        self.store, self.folder, self.author, self.state = store, folder, "package:export", {}


@pytest.fixture
def store(tmp_path):
    store = Store.create(tmp_path, "Запись к врачу без звонков", "Пациент выбирает время сам")
    store.apply([
        {"op": "add_card", "kind": "ветка", "title": "Функции", "parent": "c1", "ref": "f"},
        {"op": "add_card", "kind": "решение", "title": "Онлайн-запись", "body": "Пациент видит\nсвободные окна",
         "parent": "@f", "ref": "z",
         "decision": {"question": "Как записываться?", "options": ["Онлайн", "По звонку"],
                      "chosen": {"type": "choice", "indexes": [1], "values": ["Онлайн"], "text": "", "value": "Онлайн"}, "by": "decider",
                      "assumption": True, "rationale": "Так дешевле"}},
        {"op": "add_card", "kind": "требование", "title": "Пациент занимает окно", "parent": "@z",
         "attrs": {"formalize.code": "FR-1", "formalize.acceptance": ["Окно исчезает у других за 5 секунд"]}},
        {"op": "add_card", "kind": "граница", "title": "Мобильное приложение не делаем", "parent": "c1"},
        {"op": "add_card", "kind": "открытый вопрос", "title": "Что при отмене записи?", "parent": "@f"},
        {"op": "add_card", "kind": "решение", "title": "Сирота"},
        {"op": "add_edge", "from": "@z", "to": "c1", "kind": "уточняет"},
    ], HUMAN)
    store.apply([{"op": "add_card", "kind": "решение", "title": "Напоминания по СМС", "parent": "c2"}], "package:clarify")
    return store


def test_render(store):
    text = render(store)
    assert text.startswith("# Запись к врачу без звонков\n\nПациент выбирает время сам")
    assert "## Функции" in text
    assert "- **Онлайн-запись** — Пациент видит свободные окна _(допущение; решил агент)_" in text
    assert "  - [требование] **FR-1 Пациент занимает окно**" in text
    assert "    - ✓ Окно исчезает у других за 5 секунд" in text
    assert "**Напоминания по СМС** _(предложена, не принята)_" in text
    assert "## Вне веток" in text and "**Сирота**" in text
    assert "## Чего не делаем" in text and "## Открытые вопросы\n\n- Что при отмене записи?" in text
    assert "## Допущения" in text and "Так дешевле" in text
    assert "| Как записываться? | Онлайн | решатель, допущение |" in text
    assert "«Онлайн-запись» — уточняет → «Запись к врачу без звонков»" in text
    assert text.count("Что при отмене записи?") == 1          # открытый вопрос не попадает в дерево


def test_run_writes_file(store, tmp_path):
    result = run(Ctx(store, tmp_path))
    assert result["outcome"] == "готово" and "не принято 1" in result["summary"]
    assert (tmp_path / FILE_NAME).read_text(encoding="utf-8").startswith("# Запись к врачу")
    assert manifest()["kind"] == "code" and callable(manifest()["run"])
