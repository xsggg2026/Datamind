"""Web portal route tests: run, view, compare, delete, delete-batch."""
from __future__ import annotations

import io
import json
import re

SAMPLE = "huaxia_q2_2026.xbrl"


def _sidebar_ids(client) -> set[str]:
    html = client.get("/").get_data(as_text=True)
    return set(re.findall(r'data-run-id="([^"]+)"', html))


def _upload(client, name: str = SAMPLE) -> str:
    from tests.conftest import PROJECT_ROOT

    path = PROJECT_ROOT / "data" / "sample_xbrl" / name
    before = _sidebar_ids(client)
    resp = client.post(
        "/run",
        data={"xml_file": (io.BytesIO(path.read_bytes()), name)},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 200, resp.status_code
    new = _sidebar_ids(client) - before
    assert len(new) == 1, f"expected exactly 1 new run, got {new}"
    return new.pop()


def test_upload_then_view_shows_previews(portal):
    client, out_root = portal
    run_id = _upload(client)

    resp = client.get(f"/view/{run_id}")
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert "11表抓取结果预览" in html
    assert "表01_基本信息" in html
    assert "维度4：竞品对标" in html
    assert "维度5" not in html


def test_delete_single_run(portal):
    client, out_root = portal
    run_id = _upload(client)

    resp = client.post(f"/delete/{run_id}", headers={"X-Requested-With": "fetch"})
    assert resp.status_code == 200
    assert resp.get_json()["ok"] is True
    assert not (out_root / run_id).exists()
    assert client.get(f"/view/{run_id}").status_code == 404


def test_delete_unknown_run_404(portal):
    client, _ = portal
    resp = client.post("/delete/does_not_exist_123", headers={"X-Requested-With": "fetch"})
    assert resp.status_code == 404


def test_delete_rejects_path_traversal(portal):
    client, _ = portal
    resp = client.post("/delete/..%5Cevil", headers={"X-Requested-With": "fetch"})
    assert resp.status_code in (404, 405)


def test_delete_batch_mixed_ids(portal):
    client, out_root = portal
    ids = [_upload(client), _upload(client)]

    resp = client.post(
        "/delete-batch",
        data=json.dumps({"runs": ids + ["bogus_id"]}),
        content_type="application/json",
    )
    data = resp.get_json()
    assert resp.status_code == 200
    assert sorted(data["deleted"]) == sorted(ids)
    assert data["failed"] and data["failed"][0]["run_id"] == "bogus_id"
    for rid in ids:
        assert not (out_root / rid).exists()


def test_delete_batch_empty_selection(portal):
    client, _ = portal
    resp = client.post("/delete-batch", data=json.dumps({"runs": []}), content_type="application/json")
    assert resp.status_code == 400


def test_compare_two_runs(portal):
    client, _ = portal
    ids = [_upload(client), _upload(client)]

    resp = client.get(f"/compare?runs={ids[0]},{ids[1]}")
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert "基金规模对比" in html
    assert "<th>序号</th>" in html


def test_compare_requires_two(portal):
    client, _ = portal
    run_id = _upload(client)
    resp = client.get(f"/compare?runs={run_id}")
    assert resp.status_code == 200
    assert "请至少选择 2 个" in resp.get_data(as_text=True)


def test_index_lists_runs(portal):
    client, _ = portal
    run_id = _upload(client)
    html = client.get("/").get_data(as_text=True)
    assert run_id in html
    assert "删除选中" in html


def test_pwa_assets_served(portal):
    client, _ = portal
    assert client.get("/static/manifest.json").status_code == 200
    assert client.get("/static/icons/apple-touch-icon.png").status_code == 200
    assert client.get("/static/icons/icon-512.png").status_code == 200
    html = client.get("/").get_data(as_text=True)
    assert 'rel="manifest"' in html
    assert 'rel="apple-touch-icon"' in html
    assert "apple-mobile-web-app-capable" in html
