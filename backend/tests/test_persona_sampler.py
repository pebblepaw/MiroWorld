from mckainsey.models.phase_a import PersonaFilterRequest
from mckainsey.services.persona_sampler import PersonaSampler


def test_stream_sampler_collects_matches_without_dataset_filter_shuffle(monkeypatch):
    class FakeDataset:
        def __iter__(self):
            yield {"planning_area": "Bedok", "age": 27}
            yield {"planning_area": "Woodlands", "age": 41}
            yield {"planning_area": "Woodlands", "age": 58}
            yield {"planning_area": "Yishun", "age": 36}

    monkeypatch.setattr(
        "mckainsey.services.persona_sampler.load_dataset",
        lambda *args, **kwargs: FakeDataset(),
    )

    sampler = PersonaSampler("demo", "train")
    rows = sampler.sample(
        PersonaFilterRequest(
            limit=2,
            planning_areas=["Woodlands"],
            mode="stream",
        )
    )

    assert len(rows) == 2
    assert [row["planning_area"] for row in rows] == ["Woodlands", "Woodlands"]


def test_local_sampler_uses_downloaded_parquet(monkeypatch, tmp_path):
    parquet_dir = tmp_path / "data"
    parquet_dir.mkdir(parents=True)
    parquet_path = parquet_dir / "train-00000-of-00001.parquet"
    parquet_path.write_text("placeholder", encoding="utf-8")

    monkeypatch.setattr(
        "mckainsey.services.persona_sampler.snapshot_download",
        lambda **kwargs: str(tmp_path),
    )

    class FakeCursor:
        def fetch_df(self):
            class FakeDf:
                def to_dict(self, orient):
                    return [
                        {"planning_area": "Yishun", "age": 38, "income_bracket": "$3,000-$3,999"},
                        {"planning_area": "Woodlands", "age": 52, "income_bracket": "$2,000-$2,999"},
                    ]

            return FakeDf()

    class FakeConn:
        def execute(self, query):
            assert str(parquet_path)[:-len("00000-of-00001.parquet")] in query
            return FakeCursor()

        def close(self):
            return None

    monkeypatch.setattr("mckainsey.services.persona_sampler.duckdb.connect", lambda: FakeConn())

    sampler = PersonaSampler("demo", "train", cache_dir=str(tmp_path))
    rows = sampler.sample(
        PersonaFilterRequest(
            limit=2,
            planning_areas=["Yishun", "Woodlands"],
            mode="local",
        )
    )

    assert len(rows) == 2
    assert rows[0]["planning_area"] == "Yishun"


def test_local_sampler_retries_without_income_bracket_when_column_missing(monkeypatch, tmp_path):
    parquet_dir = tmp_path / "data"
    parquet_dir.mkdir(parents=True)
    parquet_path = parquet_dir / "train-00000-of-00001.parquet"
    parquet_path.write_text("placeholder", encoding="utf-8")

    monkeypatch.setattr(
        "mckainsey.services.persona_sampler.snapshot_download",
        lambda **kwargs: str(tmp_path),
    )

    class FakeCursor:
        def fetch_df(self):
            class FakeDf:
                def to_dict(self, orient):
                    return [{"planning_area": "Woodlands", "age": 52}]

            return FakeDf()

    class FakeConn:
        def __init__(self):
            self.calls = 0

        def execute(self, query):
            self.calls += 1
            if self.calls == 1:
                assert "income_bracket IN" in query
                raise RuntimeError('Binder Error: Referenced column "income_bracket" not found in FROM clause')
            assert "income_bracket IN" not in query
            return FakeCursor()

        def close(self):
            return None

    monkeypatch.setattr("mckainsey.services.persona_sampler.duckdb.connect", lambda: FakeConn())

    sampler = PersonaSampler("demo", "train", cache_dir=str(tmp_path))
    rows = sampler.sample(
        PersonaFilterRequest(
            limit=1,
            planning_areas=["Woodlands"],
            income_brackets=["$3,000-$5,999"],
            mode="local",
        )
    )

    assert rows == [{"planning_area": "Woodlands", "age": 52}]


def test_query_candidates_supports_dynamic_extra_filters(monkeypatch, tmp_path):
    parquet_dir = tmp_path / "data"
    parquet_dir.mkdir(parents=True)
    parquet_path = parquet_dir / "train-00000-of-00001.parquet"
    parquet_path.write_text("placeholder", encoding="utf-8")

    monkeypatch.setattr(
        "mckainsey.services.persona_sampler.snapshot_download",
        lambda **kwargs: str(tmp_path),
    )

    captured_query = {"sql": ""}

    class FakeCursor:
        def fetch_df(self):
            class FakeDf:
                def to_dict(self, orient):
                    return [{"planning_area": "Woodlands", "age": 30, "ethnicity": "Hispanic"}]

            return FakeDf()

    class FakeConn:
        def execute(self, query):
            captured_query["sql"] = query
            return FakeCursor()

        def close(self):
            return None

    monkeypatch.setattr("mckainsey.services.persona_sampler.duckdb.connect", lambda: FakeConn())

    sampler = PersonaSampler("demo", "train", cache_dir=str(tmp_path))
    rows = sampler.query_candidates(
        limit=1,
        seed=42,
        planning_areas=["Woodlands"],
        extra_filters={
            "ethnicity": ["Hispanic"],
            "housing_type": ["HDB", "Condo"],
        },
    )

    assert rows == [{"planning_area": "Woodlands", "age": 30, "ethnicity": "Hispanic"}]
    assert '"ethnicity" IN (\'Hispanic\')' in captured_query["sql"]
    assert '"housing_type" IN (\'HDB\', \'Condo\')' in captured_query["sql"]
