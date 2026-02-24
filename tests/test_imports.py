import importlib


def test_run_is_callable():
    from d2rso import run

    assert callable(run)


def test_dunder_main_import_is_safe():
    module = importlib.import_module("d2rso.__main__")

    assert hasattr(module, "run")
    assert callable(module.run)
