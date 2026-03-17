from mckainsey.models.phase_a import PersonaFilterRequest
from mckainsey.services.persona_sampler import PersonaSampler


def test_sample_stream_filters(monkeypatch):
    rows = [
        {"age": 30, "planning_area": "Woodlands", "income_bracket": "$3,000-$5,999"},
        {"age": 60, "planning_area": "Woodlands", "income_bracket": "$3,000-$5,999"},
        {"age": 40, "planning_area": "Tampines", "income_bracket": "$6,000-$8,999"},
    ]

    class FakeDataset:
        def __init__(self, data):
            self.data = data

        def filter(self, fn):
            return FakeDataset([row for row in self.data if fn(row)])

        def shuffle(self, seed, buffer_size):
            return self

        def take(self, limit):
            return self.data[:limit]

    monkeypatch.setattr(
        "mckainsey.services.persona_sampler.load_dataset",
        lambda *args, **kwargs: FakeDataset(rows),
    )

    sampler = PersonaSampler(dataset_name="demo", split="train")
    req = PersonaFilterRequest(
        min_age=25,
        max_age=55,
        planning_areas=["Woodlands"],
        income_brackets=["$3,000-$5,999"],
        limit=10,
    )

    result = sampler.sample(req)
    assert len(result) == 1
    assert result[0]["age"] == 30


def test_sql_quote_escaping():
    from mckainsey.services.persona_sampler import _sql_quote

    assert _sql_quote("O'Reilly") == "'O''Reilly'"
