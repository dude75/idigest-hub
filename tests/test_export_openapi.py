"""OpenAPI export script produces a valid schema file."""

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "web" / "openapi" / "openapi.json"
SCRIPT = ROOT / "scripts" / "export_openapi.py"


def test_export_openapi_writes_health_path():
    proc = subprocess.run(
        [sys.executable, str(SCRIPT)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr or proc.stdout
    assert OUT.is_file()
    schema = json.loads(OUT.read_text(encoding="utf-8"))
    assert "/api/v1/health" in schema.get("paths", {})
    assert schema["paths"]["/api/v1/audios"]["get"]["parameters"]
    components = schema.get("components", {}).get("schemas", {})
    assert "AudioListResponse" in components
    assert "total" in components["AudioListResponse"]["properties"]
    assert "TaskListResponse" in components
    assert "done_total" in components["TaskListResponse"]["properties"]
    get_task = schema["paths"]["/api/v1/tasks/{task_id}"]["get"]["responses"]["200"]["content"][
        "application/json"
    ]["schema"]
    assert get_task.get("$ref", "").endswith("/TaskListItem")
    transcribe_202 = schema["paths"]["/api/v1/tasks/transcribe"]["post"]["responses"]["202"]["content"][
        "application/json"
    ]["schema"]
    assert transcribe_202.get("$ref", "").endswith("/TaskListItem")
    audio_detail = schema["paths"]["/api/v1/audios/{audio_id}"]["get"]["responses"]["200"]["content"][
        "application/json"
    ]["schema"]
    assert audio_detail.get("$ref", "").endswith("/AudioDetailResponse")
    purge = schema["paths"]["/api/v1/tasks/purge"]["post"]["responses"]["200"]["content"]["application/json"][
        "schema"
    ]
    assert purge.get("$ref", "").endswith("/TaskPurgeResponse")
    me = schema["paths"]["/api/v1/me"]["get"]["responses"]["200"]["content"]["application/json"]["schema"]
    assert me.get("$ref", "").endswith("/MeResponse")
    org = schema["paths"]["/api/v1/org"]["get"]["responses"]["200"]["content"]["application/json"]["schema"]
    assert org.get("$ref", "").endswith("/OrgPublicResponse")
    share_list = schema["paths"]["/api/v1/shares"]["get"]["responses"]["200"]["content"]["application/json"][
        "schema"
    ]
    assert share_list.get("$ref", "").endswith("/ShareListResponse")
    org_users = schema["paths"]["/api/v1/org/users"]["get"]["responses"]["200"]["content"]["application/json"][
        "schema"
    ]
    assert org_users.get("$ref", "").endswith("/OrgUserListResponse")
    assert "OrgUserListResponse" in components
    assert components["OrgUserListResponse"]["properties"]["items"]["items"]["$ref"].endswith("/UserPublic")
    avail = schema["paths"]["/api/v1/org/available-tariffs"]["get"]["responses"]["200"]["content"][
        "application/json"
    ]["schema"]
    assert avail.get("$ref", "").endswith("/TariffListResponse")
    org_stats = schema["paths"]["/api/v1/org/stats"]["get"]["responses"]["200"]["content"]["application/json"][
        "schema"
    ]
    assert org_stats.get("$ref", "").endswith("/UsageStatsResponse")
    inst_stats = schema["paths"]["/api/v1/instance/stats"]["get"]["responses"]["200"]["content"]["application/json"][
        "schema"
    ]
    assert inst_stats.get("$ref", "").endswith("/InstanceUsageStatsResponse")
    org_sso = schema["paths"]["/api/v1/org/sso"]["get"]["responses"]["200"]["content"]["application/json"]["schema"]
    assert org_sso.get("$ref", "").endswith("/OrgSsoAdminResponse")
    workers = schema["paths"]["/api/v1/workers"]["get"]["responses"]["200"]["content"]["application/json"]["schema"]
    assert workers.get("$ref", "").endswith("/WorkerListResponse")
    inst_tariffs = schema["paths"]["/api/v1/tariffs"]["get"]["responses"]["200"]["content"]["application/json"]["schema"]
    assert inst_tariffs.get("$ref", "").endswith("/TariffListResponse")
    login_ok = schema["paths"]["/api/v1/auth/login"]["post"]["responses"]["200"]["content"]["application/json"]["schema"]
    assert login_ok.get("anyOf") or login_ok.get("$ref")
    refs = login_ok.get("anyOf", [])
    if refs:
        ref_names = {item.get("$ref", "").split("/")[-1] for item in refs}
        assert {"LoginOkResponse", "LoginMfaRequiredResponse"} <= ref_names
    inst_orgs = schema["paths"]["/api/v1/orgs"]["get"]["responses"]["200"]["content"]["application/json"]["schema"]
    assert inst_orgs.get("$ref", "").endswith("/InstanceOrgListResponse")
    settings = schema["paths"]["/api/v1/instance/settings"]["get"]["responses"]["200"]["content"]["application/json"]["schema"]
    assert settings.get("$ref", "").endswith("/InstanceSettingsResponse")
    delete_impact = schema["paths"]["/api/v1/workers/{worker_id}/delete-impact"]["get"]["responses"]["200"]["content"][
        "application/json"
    ]["schema"]
    assert delete_impact.get("$ref", "").endswith("/WorkerImpactResponse")
    assert "lost_model_pairs" in components["WorkerImpactResponse"]["properties"]
    pub_links = schema["paths"]["/api/v1/org/public-links"]["get"]["responses"]["200"]["content"]["application/json"][
        "schema"
    ]
    assert pub_links.get("$ref", "").endswith("/OrgPublicLinkListResponse")
