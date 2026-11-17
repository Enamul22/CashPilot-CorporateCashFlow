from streamlit.testing.v1 import AppTest

from cashpilot.config import ROOT


def button(app, label):
    return next(w for w in app.button if w.label == label)


def test_read_only_scenario_preview_and_invalid_data(monkeypatch):
    monkeypatch.setenv("CASHPILOT_MODE", "hosted")
    monkeypatch.setenv("CASHPILOT_DATABASE_URL", "")
    app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=30).run()
    assert not app.exception
    button(app, "Delay a receipt").click().run()
    assert not app.exception
    assert button(app, "Save review").disabled and button(app, "Save scenario").disabled
    assert any("outside these seven days" in c.value for c in app.caption)
    app.query_params["account"] = "CP-099"
    app.run()
    assert not app.exception and any("Forecast unavailable" in w.value for w in app.warning)


def test_ui_saved_review_scenario_refresh(monkeypatch, tmp_path):
    monkeypatch.setenv("CASHPILOT_MODE", "local")
    monkeypatch.setenv("CASHPILOT_SQLITE_PATH", str(tmp_path / "ui.sqlite"))
    app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=30).run()
    button(app, "Start a saved workspace").click().run()
    token = app.query_params["workspace"]
    button(app, "Delay a receipt").click().run()
    aid = app.query_params["account"]
    next(w for w in app.selectbox if w.label == "Review status to save").set_value("Monitoring")
    next(w for w in app.text_area if w.label == "Investigation note").set_value(
        "Confirm invoice settlement before payroll."
    )
    button(app, "Save review").click().run()
    assert not app.exception and not app.error
    next(w for w in app.text_input if w.label == "Scenario name").set_value(
        "Customer receipt postponed"
    )
    button(app, "Save scenario").click().run()
    assert not app.exception and not app.error
    returned = AppTest.from_file(str(ROOT / "app.py"), default_timeout=30)
    returned.query_params.update({"workspace": token, "account": aid})
    returned.run()
    assert not returned.exception
    assert any("Confirm invoice settlement" in w.value for w in returned.markdown)
    assert any("Customer receipt postponed" in w.value for w in returned.markdown)
