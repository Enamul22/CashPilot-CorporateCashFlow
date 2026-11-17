import pytest

from cashpilot.artifacts import bundle, forecast_index
from cashpilot.config import ROOT
from cashpilot.data import Sources
from cashpilot.repository import Repository


@pytest.fixture(scope="session")
def data():
    return bundle()


@pytest.fixture(scope="session")
def sources():
    return Sources(ROOT / "evaluation/raw")


@pytest.fixture
def record(data):
    return data["forecasts"][data["examples"]["delayed_receipt"]["account_id"]][-1]


@pytest.fixture
def repo(tmp_path, data):
    repo = Repository("sqlite:///" + str(tmp_path / "state.sqlite"))
    repo.migrate()
    repo.register(forecast_index(data).values())
    return repo
