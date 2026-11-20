import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app"

CORE_FORBIDDEN = ["sqlalchemy", "fastapi", "app.db", "app.api", "app.models", "app.repositories.sqlalchemy"]
ENDPOINT_FORBIDDEN = [
    "sqlalchemy", "app.models", "app.repositories", "app.services", "app.simulation",
]

EXPECTED_WORLD_ROUTES = {
    ("POST", "/api/v1/worlds"),
    ("GET", "/api/v1/worlds/{world_id}"),
    ("GET", "/api/v1/worlds/{world_id}/state"),
    ("GET", "/api/v1/worlds/{world_id}/chunks"),
    ("GET", "/api/v1/worlds/{world_id}/map"),
    ("GET", "/api/v1/worlds/{world_id}/buildings"),
    ("GET", "/api/v1/worlds/{world_id}/buildings/{building_id}"),
    ("GET", "/api/v1/worlds/{world_id}/citizens"),
    ("GET", "/api/v1/worlds/{world_id}/citizens/{citizen_id}"),
    ("GET", "/api/v1/worlds/{world_id}/companies"),
    ("GET", "/api/v1/worlds/{world_id}/companies/{company_id}"),
    ("GET", "/api/v1/worlds/{world_id}/companies/{company_id}/employees"),
    ("GET", "/api/v1/worlds/{world_id}/summary"),
    ("GET", "/api/v1/worlds/{world_id}/view"),
    ("GET", "/api/v1/worlds/{world_id}/metrics"),
    ("PATCH", "/api/v1/worlds/{world_id}/simulation"),
    ("PATCH", "/api/v1/worlds/{world_id}/policies"),
    ("POST", "/api/v1/worlds/{world_id}/ticks"),
}
ENGINE_ALLOWED = {
    "app/simulation/engine_adapter.py",
    "app/repositories/sqlalchemy/engine_mapper.py",
}


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            modules.add(node.module)
    return modules


def _matches(module: str, prefix: str) -> bool:
    return module == prefix or module.startswith(prefix + ".")


def _violations(paths: list[Path], forbidden: list[str]) -> list[str]:
    found = []
    for path in paths:
        for module in _imports(path):
            if any(_matches(module, prefix) for prefix in forbidden):
                found.append(f"{path.relative_to(ROOT)} imports {module}")
    return found


def test_usecases_and_services_do_not_import_frameworks_or_persistence():
    paths = list((APP / "usecases").rglob("*.py")) + list((APP / "services").rglob("*.py"))
    assert _violations(paths, CORE_FORBIDDEN) == []


def test_simulation_engine_imported_only_by_adapter_and_mapper():
    importers = {
        p.relative_to(ROOT).as_posix()
        for p in APP.rglob("*.py")
        if any(_matches(m, "simulation_engine") for m in _imports(p))
    }
    assert importers <= ENGINE_ALLOWED


def test_services_usecases_and_port_do_not_import_simulation_engine():
    paths = list((APP / "usecases").rglob("*.py")) + list((APP / "services").rglob("*.py"))
    paths.append(APP / "simulation" / "interfaces.py")
    assert _violations(paths, ["simulation_engine"]) == []


def test_endpoints_do_not_import_persistence_or_services():
    paths = list((APP / "api" / "v1" / "endpoints").rglob("*.py"))
    assert _violations(paths, ENDPOINT_FORBIDDEN) == []


def test_only_composition_root_imports_both_services_and_sqlalchemy_repositories():
    all_files = list(APP.rglob("*.py"))
    imports_services = {p for p in all_files if any(_matches(m, "app.services") for m in _imports(p))}
    imports_sqla = {
        p for p in all_files if any(_matches(m, "app.repositories.sqlalchemy") for m in _imports(p))
    }
    both = {p.relative_to(ROOT).as_posix() for p in imports_services & imports_sqla}
    assert both == {"app/api/deps.py"}


def test_world_handlers_only_return_a_use_case_call():
    tree = ast.parse((APP / "api" / "v1" / "endpoints" / "worlds.py").read_text(encoding="utf-8"))
    functions = [node for node in tree.body if isinstance(node, ast.FunctionDef)]
    assert functions
    for fn in functions:
        assert len(fn.body) == 1, f"{fn.name} must have a single statement"
        stmt = fn.body[0]
        assert isinstance(stmt, ast.Return) and isinstance(stmt.value, ast.Call), fn.name
        func = stmt.value.func
        assert (
            isinstance(func, ast.Attribute)
            and isinstance(func.value, ast.Name)
            and func.value.id == "use_case"
        ), fn.name


def test_crud_package_is_gone():
    assert not (APP / "crud").exists()


def test_world_routes_registered_under_api_v1():
    # app.routes wraps included routers (FastAPI >= 0.1xx), so read the registered paths from OpenAPI.
    from app.main import app

    paths = app.openapi()["paths"]
    registered = {(method.upper(), path) for path, ops in paths.items() for method in ops}
    assert EXPECTED_WORLD_ROUTES <= registered
    assert len({r for r in registered if r[1].startswith("/api/v1/worlds")}) == len(EXPECTED_WORLD_ROUTES)


def test_runner_package_does_not_import_infrastructure():
    paths = list((APP / "runner").rglob("*.py"))
    forbidden = ["sqlalchemy", "simulation_engine", "app.models", "app.repositories.sqlalchemy", "app.db", "fastapi"]
    assert _violations(paths, forbidden) == []


def test_maps_package_is_pure():
    paths = [p for p in (APP / "maps").rglob("*.py") if p.name != "backfill.py"]
    assert _violations(paths, ["sqlalchemy", "fastapi", "simulation_engine", "app.db", "app.models"]) == []


def test_read_schema_keys_match_frontend_dtos():
    import re

    from app.schemas.city import BuildingRead, CitizenRead, MovementRead

    fe = ROOT.parent / "frontend" / "src" / "render"

    def dto_keys(path, name):
        body = re.search(rf"interface {name} \{{(.*?)\n\}}", (fe / path).read_text(), re.S).group(1)
        return set(re.findall(r"^\s+(\w+)\??:", body, re.M))

    assert set(BuildingRead.model_fields) == dto_keys("map/types.ts", "BuildingDTO")
    assert set(CitizenRead.model_fields) >= dto_keys("citizens/types.ts", "CitizenDTO")
    # MovementRead omits citizen_id: the citizen is the enclosing object
    assert set(MovementRead.model_fields) == dto_keys("citizens/types.ts", "MovementEventDTO") - {"citizen_id"}
