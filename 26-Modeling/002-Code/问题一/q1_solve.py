"""D 题问题一：单服务区直接往返能力、精确组批与安全余量敏感性。

运行：conda run -n py310 python 26-Modeling/002-Code/问题一/q1_solve.py
仅依赖 py310 中已有的 numpy、scipy 和 openpyxl。原始题目与附件只读。
"""

from __future__ import annotations

import json
import math
import re
import zipfile
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from xml.sax.saxutils import escape

import numpy as np
from openpyxl import load_workbook
from scipy.io import loadmat
from scipy.optimize import brentq


def find_project_root() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "26-Modeling/001-Issue/D题").is_dir():
            return parent
    raise FileNotFoundError("无法从脚本位置向上找到 26-Modeling/001-Issue/D题")


ROOT = find_project_root()
ISSUE = ROOT / "26-Modeling/001-Issue/D题"
DATA = ISSUE / "数据/无人机应急物资运输基础数据"
GEO = ISSUE / "数据/镇龙乡地理空间数据"
OUT = Path(__file__).resolve().parent
G = 9.80665  # 标准重力加速度，m/s²
R_EARTH = 6_371_000.0  # 球面大圆距离，m
EPS = 1e-9


@dataclass(frozen=True)
class Drone:
    code: str
    empty_mass: float
    max_mass: float
    max_volume: float
    speed: float
    empty_range: float
    full_range: float
    energy: float
    reserve: float
    prepare: float
    load_per_box: float
    handoff_base: float
    handoff_per_box: float
    ascend_speed: float
    descend_speed: float
    ascend_eff: float


def source_data():
    nodes_ws = load_workbook(DATA / "调度中心与服务区.xlsx", read_only=True, data_only=True).active
    nodes = {}
    for row in nodes_ws.iter_rows(values_only=True):
        if isinstance(row[0], str) and (row[0] == "O01" or row[0].startswith("S")):
            nodes[row[0]] = (float(row[2]), float(row[3]), float(row[4]))
    assert len(nodes) == 16

    drones_ws = load_workbook(DATA / "运输无人机数据.xlsx", read_only=True, data_only=True).active
    drones = {}
    for row in drones_ws.iter_rows(values_only=True):
        if row[0] in {"A", "B", "C"} and isinstance(row[3], (int, float)):
            drones[row[0]] = Drone(
                row[0], *map(float, (row[2], row[3], row[4], row[5], row[6], row[7], row[8])),
                float(row[9]) / 100,
                *map(float, (row[10], row[11], row[12], row[13], row[14], row[15], row[16])),
            )
    assert len(drones) == 3

    book = load_workbook(DATA / "物资需求与配送时限.xlsx", read_only=True, data_only=True)
    demands = {}
    for row in list(book["数据"].iter_rows(values_only=True))[1:]:
        if row[0]:
            demands[(row[0], row[1])] = int(row[2])
    boxes = defaultdict(list)
    for row in list(book["逐箱货箱清单"].iter_rows(values_only=True))[1:]:
        if row[0]:
            boxes[row[1]].append({
                "id": row[0], "zone": row[1], "type": row[2],
                "mass": float(row[3]), "volume": float(row[4]),
                "first": row[5] == "是", "first_deadline_s": row[6],
                "expected_s": row[7], "priority": row[8],
            })
    assert len(boxes) == 15 and sum(map(len, boxes.values())) == 80
    assert len({b["id"] for bs in boxes.values() for b in bs}) == 80
    assert Counter((b["zone"], b["type"]) for bs in boxes.values() for b in bs) == demands
    return nodes, drones, dict(boxes)


def dem_data():
    mat = loadmat(next(GEO.rglob("*DEM.mat")))
    dem = mat["dem"]
    lon = mat["longitude"][0]
    lat = mat["latitude"][:, 0]
    assert dem.shape == (len(lat), len(lon))
    assert int(mat["epsg_code"][0, 0]) == 4326
    assert np.isfinite(dem).all() and dem.min() > 0
    return dem, lon, lat


def _segment_touches_cell(x0, y0, x1, y1, c, r):
    """Liang–Barsky 闭方格相交测试；触及边界的像元也计入。"""
    dx, dy = x1 - x0, y1 - y0
    lo, hi = 0.0, 1.0
    for origin, delta, minimum, maximum in (
        (x0, dx, c - 0.5, c + 0.5),
        (y0, dy, r - 0.5, r + 0.5),
    ):
        if abs(delta) < 1e-14:
            if origin < minimum - 1e-12 or origin > maximum + 1e-12:
                return False
        else:
            a, b = (minimum - origin) / delta, (maximum - origin) / delta
            lo, hi = max(lo, min(a, b)), min(hi, max(a, b))
            if lo > hi + 1e-12:
                return False
    return True


def route_dem_max(p0, p1, dem, lon, lat):
    x0 = (p0[0] - lon[0]) / (lon[1] - lon[0])
    x1 = (p1[0] - lon[0]) / (lon[1] - lon[0])
    y0 = (lat[0] - p0[1]) / (lat[0] - lat[1])
    y1 = (lat[0] - p1[1]) / (lat[0] - lat[1])
    cols = range(max(0, math.floor(min(x0, x1) - 0.5)),
                 min(dem.shape[1] - 1, math.ceil(max(x0, x1) + 0.5)) + 1)
    rows = range(max(0, math.floor(min(y0, y1) - 0.5)),
                 min(dem.shape[0] - 1, math.ceil(max(y0, y1) + 0.5)) + 1)
    values = [float(dem[r, c]) for r in rows for c in cols
              if _segment_touches_cell(x0, y0, x1, y1, c, r)]
    assert values
    return max(values), len(values)


def haversine(p0, p1):
    lon0, lat0, _ = p0
    lon1, lat1, _ = p1
    a = math.sin(math.radians(lat1 - lat0) / 2) ** 2
    a += math.cos(math.radians(lat0)) * math.cos(math.radians(lat1)) * math.sin(math.radians(lon1 - lon0) / 2) ** 2
    return 2 * R_EARTH * math.asin(math.sqrt(a))


def geometry(nodes, dem, lon, lat):
    out = {}
    origin = nodes["O01"]
    for zone in sorted(k for k in nodes if k != "O01"):
        target = nodes[zone]
        maximum, ncell = route_dem_max(origin, target, dem, lon, lat)
        altitude = max(maximum + 50, origin[2], target[2] + 30)
        out[zone] = {
            "distance_m": haversine(origin, target), "max_dem_m": maximum,
            "dem_cell_count": ncell, "cruise_altitude_m": altitude,
            "out_up_m": altitude - origin[2], "out_down_m": altitude - target[2] - 30,
            "back_up_m": altitude - target[2] - 30, "back_down_m": altitude - origin[2],
        }
    return out


def flight_time(drone, geo):
    return ((geo["out_up_m"] + geo["back_up_m"]) / drone.ascend_speed
            + 2 * geo["distance_m"] / drone.speed
            + (geo["out_down_m"] + geo["back_down_m"]) / drone.descend_speed)


def equivalent_range(drone, mass):
    return drone.empty_range - (drone.empty_range - drone.full_range) * (mass / drone.max_mass) ** 1.5


def flight_energy(drone, geo, mass):
    d = geo["distance_m"]
    horizontal = drone.energy * d / equivalent_range(drone, mass)
    horizontal += drone.energy * d / drone.empty_range
    climb_j = ((drone.empty_mass + mass) * G * geo["out_up_m"]
               + drone.empty_mass * G * geo["back_up_m"])
    return horizontal + climb_j / (drone.ascend_eff * 3_600_000)


def safe_mass(drone, geo, reserve):
    limit = (1 - reserve) * drone.energy
    if flight_energy(drone, geo, 0) > limit + EPS:
        return None
    if flight_energy(drone, geo, drone.max_mass) <= limit + EPS:
        return drone.max_mass
    return brentq(lambda q: flight_energy(drone, geo, q) - limit, 0, drone.max_mass, xtol=1e-10)


def trip(drone, geo, subset, reserve):
    mass = sum(box["mass"] for box in subset)
    volume = sum(box["volume"] for box in subset)
    if mass > drone.max_mass + EPS or volume > drone.max_volume + EPS:
        return None
    energy = flight_energy(drone, geo, mass)
    if energy > (1 - reserve) * drone.energy + EPS:
        return None
    n = len(subset)
    flying = flight_time(drone, geo)
    working = flying + drone.prepare + n * drone.load_per_box + drone.handoff_base + n * drone.handoff_per_box
    return {"model": drone.code, "box_ids": [b["id"] for b in subset],
            "mass_kg": mass, "volume_m3": volume, "flight_s": flying,
            "operation_s": working, "energy_kwh": energy,
            "return_soc_pct": 100 * (1 - energy / drone.energy)}


def optimize_zone(boxes, drones, geo, reserve, objective):
    """枚举所有非空子集；锚定最小编号箱子的集合划分 DP 消除排列重复。"""
    n = len(boxes)
    size = 1 << n
    mass = [0.0] * size
    volume = [0.0] * size
    count = [0] * size
    for mask in range(1, size):
        bit = mask & -mask
        i = bit.bit_length() - 1
        prev = mask ^ bit
        mass[mask] = mass[prev] + boxes[i]["mass"]
        volume[mask] = volume[prev] + boxes[i]["volume"]
        count[mask] = count[prev] + 1

    ordered = sorted(drones.values(), key=lambda d: d.code)
    choices = [None] * size
    for mask in range(1, size):
        best = None
        for d in ordered:
            if mass[mask] > d.max_mass + EPS or volume[mask] > d.max_volume + EPS:
                continue
            e = flight_energy(d, geo, mass[mask])
            if e > (1 - reserve) * d.energy + EPS:
                continue
            t = (flight_time(d, geo) + d.prepare + count[mask] * d.load_per_box
                 + d.handoff_base + count[mask] * d.handoff_per_box)
            key = ((e, t, d.code) if objective == "energy"
                   else (t, e, d.code) if objective == "time"
                   else (e, t, d.code))
            if best is None or key < best[0]:
                best = (key, d.code, e, t)
        choices[mask] = best

    inf = (math.inf, math.inf, math.inf)
    dp = [inf] * size
    picked = [None] * size
    dp[0] = (0, 0.0, 0.0)
    for mask in range(1, size):
        anchor = mask & -mask
        sub = mask
        while sub:
            if sub & anchor and choices[sub] is not None:
                rest = dp[mask ^ sub]
                if math.isfinite(rest[0]):
                    _, code, e, t = choices[sub]
                    trips = rest[0] + 1
                    energy = rest[1] + e
                    time = rest[2] + t
                    key = ((energy, trips, time) if objective == "energy"
                           else (time, trips, energy) if objective == "time"
                           else (trips, energy, time))
                    current = ((dp[mask][1], dp[mask][0], dp[mask][2]) if objective == "energy"
                               else (dp[mask][2], dp[mask][0], dp[mask][1]) if objective == "time"
                               else dp[mask])
                    if key < current:
                        dp[mask] = (trips, energy, time)
                        picked[mask] = (sub, code)
            sub = (sub - 1) & mask
    if not math.isfinite(dp[-1][0]):
        raise ValueError(f"服务区 {boxes[0]['zone']} 在返航余量 {reserve:.0%} 下无法完成全部货箱")

    answer = []
    mask = size - 1
    while mask:
        sub, code = picked[mask]
        selected = [boxes[i] for i in range(n) if sub & (1 << i)]
        answer.append(trip(drones[code], geo, selected, reserve))
        mask ^= sub
    # 同类货箱物理参数相同；先安排其较小编号以便首批保障箱后续衔接问题二。
    answer.sort(key=lambda x: (x["mass_kg"], x["model"], x["box_ids"]))
    by_type = defaultdict(list)
    type_order = []
    type_of = {}
    for b in boxes:
        if b["type"] not in by_type:
            type_order.append(b["type"])
        by_type[b["type"]].append(b["id"])
        type_of[b["id"]] = b["type"]
    for row in answer:
        counts = Counter(type_of[bid] for bid in row["box_ids"])
        row["box_ids"] = []
        for name in type_order:
            take = counts[name]
            row["box_ids"].extend(by_type[name][:take])
            del by_type[name][:take]
    return answer


def scenario(nodes, drones, boxes, geos, reserve, objective):
    answer = []
    for zone in sorted(boxes):
        for trip_result in optimize_zone(boxes[zone], drones, geos[zone], reserve, objective):
            trip_result["zone"] = zone
            answer.append(trip_result)
    for i, row in enumerate(answer, 1):
        row["trip_id"] = f"Q1-{i:03d}"
    ids = [bid for row in answer for bid in row["box_ids"]]
    assert len(ids) == len(set(ids)) == 80
    assert set(ids) == {b["id"] for group in boxes.values() for b in group}
    for row in answer:
        d = drones[row["model"]]
        assert row["mass_kg"] <= d.max_mass + EPS
        assert row["volume_m3"] <= d.max_volume + EPS
        assert row["return_soc_pct"] >= 100 * reserve - 1e-7
        assert all(bid.startswith(row["zone"] + "-") for bid in row["box_ids"])
    metrics = {
        "reserve_pct": reserve * 100, "objective": objective,
        "trip_count": len(answer),
        "energy_kwh": sum(row["energy_kwh"] for row in answer),
        "flight_s": sum(row["flight_s"] for row in answer),
        "operation_s": sum(row["operation_s"] for row in answer),
        "models": dict(Counter(row["model"] for row in answer)),
    }
    return {"metrics": metrics, "trips": answer}


def write_q1_template(trips):
    """只替换模板的 Q1 工作表 XML；其他 ZIP 成员内容完全保留。"""
    source = ISSUE / "结果提交模板.xlsx"
    target = OUT / "问题一结果_模板填写版.xlsx"
    with zipfile.ZipFile(source, "r") as original, zipfile.ZipFile(target, "w") as output:
        for info in original.infolist():
            payload = original.read(info.filename)
            if info.filename == "xl/worksheets/sheet1.xml":
                xml = payload.decode("utf-8")
                xml, changed = re.subn(r'<dimension ref="[^"]+"/>',
                                       f'<dimension ref="A1:I{len(trips)+1}"/>', xml, count=1)
                assert changed == 1
                match = re.search(r"<sheetData>(.*?)</sheetData>", xml, flags=re.DOTALL)
                assert match is not None
                header = re.search(r'<row r="1".*?</row>', match.group(1), flags=re.DOTALL)
                assert header is not None
                rows_xml = [header.group(0)]
                for row_num, item in enumerate(trips, 2):
                    values = [item["trip_id"], item["zone"], item["model"],
                              ",".join(item["box_ids"]), item["mass_kg"],
                              item["volume_m3"], item["flight_s"],
                              item["energy_kwh"], item["return_soc_pct"]]
                    cells = []
                    for col, value in zip("ABCDEFGHI", values):
                        ref = f"{col}{row_num}"
                        if isinstance(value, str):
                            cells.append(f'<c r="{ref}" s="7" t="inlineStr"><is><t>{escape(value)}</t></is></c>')
                        else:
                            cells.append(f'<c r="{ref}" s="7"><v>{value:.15g}</v></c>')
                    rows_xml.append(f'<row r="{row_num}" spans="1:9">{"".join(cells)}</row>')
                xml = xml[:match.start()] + "<sheetData>" + "".join(rows_xml) + "</sheetData>" + xml[match.end():]
                payload = xml.encode("utf-8")
            elif info.filename == "xl/workbook.xml":
                xml = payload.decode("utf-8")
                xml, changed = re.subn(r'activeTab="\d+"', 'activeTab="0"', xml, count=1)
                assert changed == 1
                payload = xml.encode("utf-8")
            output.writestr(info, payload)
    with zipfile.ZipFile(source) as original, zipfile.ZipFile(target) as generated:
        assert original.namelist() == generated.namelist()
        for name in original.namelist():
            if name not in {"xl/worksheets/sheet1.xml", "xl/workbook.xml"}:
                assert original.read(name) == generated.read(name), name
    check = load_workbook(target, read_only=True, data_only=True)
    assert check.sheetnames[0] == "Q1_单点组批"
    actual = list(check.worksheets[0].iter_rows(min_row=2, max_row=len(trips) + 1, max_col=9, values_only=True))
    assert len(actual) == len(trips)
    for row, expected in zip(actual, trips):
        assert row[0] == expected["trip_id"] and row[1] == expected["zone"]
        assert row[2] == expected["model"] and row[3].split(",") == expected["box_ids"]
        assert abs(row[7] - expected["energy_kwh"]) < 1e-10
    return target


def main():
    nodes, drones, boxes = source_data()
    dem, lon, lat = dem_data()
    geos = geometry(nodes, dem, lon, lat)
    reserves = [0.1, 0.2, 0.3, 0.4]
    capacities = []
    for reserve in reserves:
        for zone in sorted(boxes):
            for code in sorted(drones):
                d = drones[code]
                q = safe_mass(d, geos[zone], reserve)
                capacities.append({"reserve_pct": reserve * 100, "zone": zone, "model": code,
                                   "safe_mass_kg": q, "max_volume_m3": d.max_volume,
                                   "empty_trip_feasible": q is not None,
                                   "distance_m": geos[zone]["distance_m"],
                                   "max_dem_m": geos[zone]["max_dem_m"],
                                   "cruise_altitude_m": geos[zone]["cruise_altitude_m"]})
    scenarios = {}
    for objective in ["lexicographic", "energy", "time"]:
        scenarios[f"20pct_{objective}"] = scenario(nodes, drones, boxes, geos, 0.2, objective)
    for reserve in [0.1, 0.3, 0.4]:
        try:
            scenarios[f"{int(reserve*100)}pct_lexicographic"] = scenario(
                nodes, drones, boxes, geos, reserve, "lexicographic")
        except ValueError as exc:
            scenarios[f"{int(reserve*100)}pct_lexicographic"] = {"error": str(exc)}
    result = {"method": {"distance": "WGS84 球面 Haversine，地球半径 6371000 m",
                         "dem": "MAT 栅格中心坐标；线段接触的全部闭像元取最大值",
                         "gravity_m_s2": G,
                         "horizontal_energy": "Euse*d/L(q)，去程 q，返程 0",
                         "climb_energy": "(m0+q)*g*h_up/(eta*3.6e6)",
                         "operation_time": "飞行+固定准备+逐箱装载+基础交接+逐箱交接；不含设备/电池周转"},
              "geometry": geos, "capacities": capacities, "scenarios": scenarios}
    target = OUT / "q1_results.json"
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("结果：", target)
    workbook = write_q1_template(scenarios["20pct_lexicographic"]["trips"])
    print("结果模板：", workbook)
    for key, value in scenarios.items():
        print(key, value.get("metrics", value.get("error")))
    for row in scenarios["20pct_lexicographic"]["trips"][:5]:
        print(row)


if __name__ == "__main__":
    main()
