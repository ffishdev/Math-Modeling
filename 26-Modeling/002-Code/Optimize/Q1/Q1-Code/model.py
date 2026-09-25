"""Q1 physical model and exact count-state Pareto DP, adapted from Q1.ipynb.
Original notebook is preserved. Input files are never modified.
"""
import math, itertools, bisect
from pathlib import Path
import numpy as np
import pandas as pd
import scipy.io as sio
PROJECT = next(p for p in Path(__file__).resolve().parents if (p/'26-Modeling/001-Issue/D题').exists())
BASE_DIR = PROJECT/'26-Modeling/001-Issue/D题'
def find_file(name):
    hits=list(BASE_DIR.rglob(name))
    if len(hits)!=1: raise ValueError((name,len(hits)))
    return hits[0]
def read_block(df, title):
    """从块状 Excel 中读取名为 title 的数据块（标题行 → 表头行 → 数据行 → 空行）。"""
    col0 = df[0].astype(str).str.strip()
    idx = int(col0.index[col0 == title][0])
    header = [str(h).strip() for h in df.iloc[idx + 1].tolist()]
    rows = []
    for k in range(idx + 2, len(df)):
        r = df.iloc[k]
        if r.isna().all():
            break
        rows.append(r.tolist())
    out = pd.DataFrame(rows, columns=header).dropna(axis=1, how='all')
    return out.loc[:, [c for c in out.columns if c != 'nan']].reset_index(drop=True)

raw_node = pd.read_excel(find_file('调度中心与服务区.xlsx'), header=None)
depot = read_block(raw_node, '调度中心').rename(columns={'调度中心编号': 'id', '调度中心名称': 'name', '经度（°）': 'lon', '纬度（°）': 'lat', '海拔（m）': 'elev'})
areas = read_block(raw_node, '服务区').rename(columns={'服务区编号': 'id', '服务区名称': 'name', '经度（°）': 'lon', '纬度（°）': 'lat', '海拔（m）': 'elev', '本次需保障人口（人）': 'pop'})
for c in ('lon', 'lat', 'elev'):
    depot[c] = pd.to_numeric(depot[c])
    areas[c] = pd.to_numeric(areas[c])
areas['pop'] = pd.to_numeric(areas['pop']).astype(int)
AREA_IDS = areas['id'].tolist()
(LON_O, LAT_O, Z_O) = depot.loc[0, ['lon', 'lat', 'elev']].astype(float)
raw_uav = pd.read_excel(find_file('运输无人机数据.xlsx'), header=None)
uav_cols = {'机型编号': 'g', '机型名称': 'name', '含电池空载总质量（kg）': 'm0', '最大载货质量（kg）': 'Q', '可用装载体积（m³）': 'V', '计划巡航速度（m/s）': 'v_c', '空载标准航程（m）': 'L0', '满载标准航程（m）': 'LF', '电池可用能量（kWh）': 'E_use', '返航电量下限（%）': 'rho_pct', '工位固定准备时间（s）': 't_prep', '每箱装载时间（s）': 't_load', '接收点基础交接时间（s）': 't_hand', '每箱增加交接时间（s）': 't_box', '最大爬升速度（m/s）': 'v_up', '最大下降速度（m/s）': 'v_dn', '爬升能耗效率': 'eta_up', '下降能耗效率': 'eta_dn'}
uav = read_block(raw_uav, '三类机型参数').rename(columns=uav_cols)
for c in uav.columns.difference(['g', 'name']):
    uav[c] = pd.to_numeric(uav[c])
uav['rho'] = uav['rho_pct'] / 100
uav = uav.set_index('g')
TYPES = uav.index.tolist()
fleet = read_block(raw_uav, '逐架无人机清单')
battery = read_block(raw_uav, '共享电池库存')
demand_path = find_file('物资需求与配送时限.xlsx')
demand = pd.read_excel(demand_path, sheet_name='数据')
boxes = pd.read_excel(demand_path, sheet_name='逐箱货箱清单').rename(columns={'货箱编号': 'box', '服务区编号': 'area', '物资类型': 'mat', '单箱质量（kg）': 'mass', '单箱体积（m³）': 'vol', '是否首批保障': 'first', '首批截止时间（s）': 'deadline', '期望送达时间（s）': 'expected', '应急优先系数': 'priority'})
boxes['first'] = boxes['first'].eq('是')
boxes['mass'] = pd.to_numeric(boxes['mass'])
boxes['vol'] = pd.to_numeric(boxes['vol'])
MAT_ORDER = ['医疗物资', '饮用水', '应急食品', '生活卫生用品']

def load_dem():
    try:
        m = sio.loadmat(find_file('镇龙乡及周边30米DEM.mat'))
        dem = m['dem'].astype(np.float32)
        tr = m['transform'].ravel()
        nodata = float(np.ravel(m['nodata'])[0])
        (dx, lon0, dy, lat0) = (float(tr[0]), float(tr[2]), float(-tr[4]), float(tr[5]))
        src = 'MAT'
    except Exception:
        import tifffile
        with tifffile.TiffFile(find_file('镇龙乡及周边30米DEM.tif')) as tf:
            page = tf.pages[0]
            dem = page.asarray().astype(np.float32)
            (sx, sy, _) = page.tags['ModelPixelScaleTag'].value
            tp = page.tags['ModelTiepointTag'].value
            (dx, dy, lon0, lat0) = (float(sx), float(sy), float(tp[3]), float(tp[4]))
            nodata = float(page.tags['GDAL_NODATA'].value) if 'GDAL_NODATA' in page.tags else -32767.0
        src = 'GeoTIFF'
    dem[dem == nodata] = np.nan
    return (dem, dict(dx=dx, dy=dy, lon0=lon0, lat0=lat0, src=src))
(DEM, GEO) = load_dem()
(NROW, NCOL) = DEM.shape
roads = pd.read_csv(find_file('镇龙乡及周边道路.csv'), encoding='utf-8-sig')
water = pd.read_csv(find_file('镇龙乡及周边水体.csv'), encoding='utf-8-sig')
rivers = pd.read_csv(find_file('镇龙乡及周边水系.csv'), encoding='utf-8-sig')
places = pd.read_csv(find_file('镇龙乡及周边村镇点位.csv'), encoding='utf-8-sig')
LON_C = GEO['lon0'] + (np.arange(NCOL) + 0.5) * GEO['dx']
LAT_C = GEO['lat0'] - (np.arange(NROW) + 0.5) * GEO['dy']

def to_pix(lon, lat):
    return ((lon - GEO['lon0']) / GEO['dx'], (GEO['lat0'] - lat) / GEO['dy'])

def dem_at(lon, lat):
    (x, y) = to_pix(lon, lat)
    return float(DEM[int(math.floor(y)), int(math.floor(x))])
assert len(depot) == 1 and len(areas) == 15 and (len(boxes) == 80)
assert boxes.box.is_unique and set(boxes.area) == set(AREA_IDS)
assert TYPES == ['A', 'B', 'C'] and DEM.shape == (1309, 1486)
ledger = pd.DataFrame([['调度中心与服务区.xlsx', '节点编号/名称/经纬度/海拔/需保障人口', 'WGS84 °、m、人', '任务 1–4（航段几何、地图）'], ['运输无人机数据.xlsx', '机型质量/载荷/体积/速度/航程/能量/效率/作业时间', 'kg、m³、m/s、m、kWh、s', '任务 1–4（能耗与时间模型）'], ['物资需求与配送时限.xlsx（逐箱货箱清单）', '80 箱；所属服务区、物资类型、质量、体积、是否首批、时限', 'kg、m³、s', '任务 2–4（组批）'], ['镇龙乡及周边30米DEM.mat/.tif', f'{NROW}×{NCOL} 高程栅格、Copernicus GLO-30 (DSM)', 'm、EPSG:4326', '任务 1（巡航海拔、爬升高度）'], ['道路/水体/水系/村镇点位.csv', '态势图背景要素（本问不参与计算）', '°', '数据可视化']], columns=['文件', '内容', '单位/坐标', '支撑的子任务'])
chk = areas[['id', 'name', 'lon', 'lat', 'elev', 'pop']].copy()
chk['DEM高程'] = [dem_at(a, b) for (a, b) in zip(chk.lon, chk.lat)]
chk['差值'] = chk['elev'] - chk['DEM高程']
node_check = chk
box_sum = boxes.groupby(['area', 'mat']).agg(箱数=('box', 'size'), 总质量kg=('mass', 'sum'), 总体积m3=('vol', 'sum'), 首批箱数=('first', 'sum'))
area_sum = boxes.groupby('area').agg(箱数=('box', 'size'), 总质量kg=('mass', 'sum'), 总体积m3=('vol', 'sum')).reindex(AREA_IDS)

(A_WGS, F_WGS) = (6378137.0, 1 / 298.257223563)
E2_WGS = 2 * F_WGS - F_WGS ** 2

def dist_m(lon0, lat0, lon1, lat1):
    phi = math.radians((lat0 + lat1) / 2)
    s2 = math.sin(phi) ** 2
    M = A_WGS * (1 - E2_WGS) / (1 - E2_WGS * s2) ** 1.5
    N = A_WGS / math.sqrt(1 - E2_WGS * s2)
    return math.hypot(math.radians(lat1 - lat0) * M, math.radians(lon1 - lon0) * N * math.cos(phi))

def traverse_cells(x0, y0, x1, y1):
    (ix, iy) = (math.floor(x0), math.floor(y0))
    (dx, dy) = (x1 - x0, y1 - y0)
    (sx, sy) = (1 if dx > 0 else -1, 1 if dy > 0 else -1)
    tdx = abs(1 / dx) if dx else math.inf
    tdy = abs(1 / dy) if dy else math.inf
    tmx = ((ix + 1 - x0) / dx if dx > 0 else (ix - x0) / dx) if dx else math.inf
    tmy = ((iy + 1 - y0) / dy if dy > 0 else (iy - y0) / dy) if dy else math.inf
    cells = [(iy, ix)]
    while len(cells) < 100000:
        if tmx < tmy:
            if tmx > 1:
                break
            ix += sx
            tmx += tdx
        else:
            if tmy > 1:
                break
            iy += sy
            tmy += tdy
        cells.append((iy, ix))
    return cells
(CLEARANCE, H_SERVICE) = (50.0, 30.0)

def segment_geometry(lon, lat, z_s, n_profile=400):
    d = dist_m(LON_O, LAT_O, lon, lat)
    (x0, y0) = to_pix(LON_O, LAT_O)
    (x1, y1) = to_pix(lon, lat)
    cells = traverse_cells(x0, y0, x1, y1)
    z = np.array([DEM[r, c] for (r, c) in cells])
    k = int(np.nanargmax(z))
    zmax = float(z[k])
    (rm, cm) = cells[k]
    Hc = zmax + CLEARANCE
    ts = np.linspace(0, 1, n_profile)
    profile = np.array([DEM[int(math.floor(y0 + (y1 - y0) * t)), int(math.floor(x0 + (x1 - x0) * t))] for t in ts])
    return dict(d=d, n_cells=len(cells), zmax=zmax, Hc=Hc, hup_out=Hc - Z_O, hdn_out=Hc - (z_s + H_SERVICE), hup_ret=Hc - (z_s + H_SERVICE), hdn_ret=Hc - Z_O, s_max=dist_m(LON_O, LAT_O, LON_C[cm], LAT_C[rm]), profile=profile)
SEG = {r.id: segment_geometry(r.lon, r.lat, r.elev) for r in areas.itertuples()}
seg_df = pd.DataFrame([dict(area=a, name=areas.set_index('id').loc[a, 'name'], **{k: v for (k, v) in g.items() if k != 'profile'}) for (a, g) in SEG.items()]).set_index('area')
assert (seg_df[['hup_out', 'hdn_out', 'hup_ret', 'hdn_ret']] >= 0).all().all()

G0 = 9.81

def L_eq(p, q):
    return p.L0 - (p.L0 - p.LF) * (q / p.Q) ** 1.5

def E_hor(p, d, q):
    return d * p.E_use / L_eq(p, q)

def E_up(p, h_up, q):
    return (p.m0 + q) * G0 * h_up / (p.eta_up * 3600000.0)

def leg_time(p, d, h_up, h_dn):
    return h_up / p.v_up + d / p.v_c + h_dn / p.v_dn

def sortie_energy_parts(p, g, q):
    return (E_hor(p, g['d'], q), E_up(p, g['hup_out'], q), E_hor(p, g['d'], 0), E_up(p, g['hup_ret'], 0))

def sortie_energy(p, g, q):
    return sum(sortie_energy_parts(p, g, q))

def sortie_flight_time(p, g):
    return leg_time(p, g['d'], g['hup_out'], g['hdn_out']) + leg_time(p, g['d'], g['hup_ret'], g['hdn_ret'])

def sortie_time(p, g, n_box):
    return p.t_prep + n_box * p.t_load + sortie_flight_time(p, g) + p.t_hand + n_box * p.t_box

def max_safe_payload(p, g, rho=None, iters=60):
    rho = p.rho if rho is None else rho
    budget = (1 - rho) * p.E_use
    if sortie_energy(p, g, 0) > budget + 1e-12:
        return (float('nan'), '不可行')
    if sortie_energy(p, g, p.Q) <= budget + 1e-12:
        return (float(p.Q), '结构载荷')
    (lo, hi) = (0.0, float(p.Q))
    for _ in range(iters):
        mid = (lo + hi) / 2
        if sortie_energy(p, g, mid) <= budget:
            lo = mid
        else:
            hi = mid
    return (lo, '能量')

def compute_qmax(rho_map=None):
    q = pd.DataFrame(index=AREA_IDS, columns=TYPES, dtype=float)
    b = q.copy().astype(object)
    for name in TYPES:
        p = uav.loc[name]
        rho = None if rho_map is None else rho_map[name]
        for a in AREA_IDS:
            (q.loc[a, name], b.loc[a, name]) = max_safe_payload(p, SEG[a], rho)
    return (q, b)
(QMAX, QBIND) = compute_qmax()
tbl = QMAX.round(2).astype(str) + ' (' + QBIND.replace({'结构载荷': '结构', '能量': '能量', '不可行': '×'}) + ')'
tbl.insert(0, '距离_km', (seg_df.d / 1000).round(2))
tbl.insert(1, '巡航海拔_m', seg_df.Hc.round(0))
parts = []
for name in TYPES:
    for a in AREA_IDS:
        q = QMAX.loc[a, name]
        if pd.notna(q):
            (eh1, eu1, eh2, eu2) = sortie_energy_parts(uav.loc[name], SEG[a], q)
            parts.append(dict(area=a, model=name, out_hor=eh1, out_up=eu1, ret_hor=eh2, ret_up=eu2))
energy_parts_df = pd.DataFrame(parts)

def pareto_filter(cands, eps=1e-09):
    """按 N、E 排序，用每层的前缀最小 T 筛除三目标支配点。候选前 3 项为 N/E/T。"""
    cands.sort(key=lambda c: (c[0], c[1], c[2]))
    layers = {}
    kept = []
    for c in cands:
        (N, E, T) = c[:3]
        dominated = False
        for (level, (Es, Ts)) in layers.items():
            if level > N:
                continue
            k = bisect.bisect_right(Es, E + eps)
            if k and Ts[k - 1] <= T + eps:
                dominated = True
                break
        if dominated:
            continue
        kept.append(c)
        (Es, Ts) = layers.setdefault(N, ([], []))
        Es.append(E)
        Ts.append(min(T, Ts[-1]) if Ts else T)
    return kept

class AreaBatching:

    def __init__(self, area_id, qmax_row, allowed=None):
        self.area = area_id
        self.geom = SEG[area_id]
        b = boxes[boxes.area == area_id]
        cls = b.groupby('mat').agg(mass=('mass', 'first'), vol=('vol', 'first'), n=('box', 'size')).reindex(MAT_ORDER).dropna()
        self.mats = cls.index.tolist()
        self.m = cls.mass.to_numpy()
        self.v = cls.vol.to_numpy()
        self.r0 = tuple((int(x) for x in cls.n.to_numpy()))
        self.allowed = TYPES if allowed is None else list(allowed)
        candidates = []
        for name in self.allowed:
            p = uav.loc[name]
            cap = qmax_row[name]
            if pd.isna(cap):
                continue
            for nvec in itertools.product(*(range(x + 1) for x in self.r0)):
                if not any(nvec):
                    continue
                mass = float(np.dot(nvec, self.m))
                vol = float(np.dot(nvec, self.v))
                if mass <= cap + 1e-09 and vol <= p.V + 1e-09:
                    candidates.append(dict(g=name, n=nvec, mass=mass, vol=vol, nbox=sum(nvec), E=sortie_energy(p, self.geom, mass), T=sortie_time(p, self.geom, sum(nvec))))
        by = {}
        for pt in candidates:
            by.setdefault(pt['n'], []).append(pt)
        self.pats = []
        for group in by.values():
            for (j, p) in enumerate(group):
                dom = any((o['E'] <= p['E'] + 1e-09 and o['T'] <= p['T'] + 1e-09 and (o['E'] < p['E'] - 1e-09 or o['T'] < p['T'] - 1e-09 or k < j) for (k, o) in enumerate(group) if k != j))
                if not dom:
                    self.pats.append(p)
        zero = (0,) * len(self.r0)
        self.memo = {zero: [(0, 0.0, 0.0, None)]}
        self.front = self._F(self.r0) if self.pats else []

    def _F(self, r):
        if r in self.memo:
            return self.memo[r]
        cands = []
        for (pid, pt) in enumerate(self.pats):
            if all((n <= ri for (n, ri) in zip(pt['n'], r))):
                child = tuple((ri - n for (n, ri) in zip(pt['n'], r)))
                for (idx, c) in enumerate(self._F(child)):
                    cands.append((c[0] + 1, c[1] + pt['E'], c[2] + pt['T'], (pid, child, idx)))
        self.memo[r] = pareto_filter(cands)
        return self.memo[r]

    def reconstruct(self, point, qmax_df):
        raw = []
        c = point
        while c[3] is not None:
            (pid, child, idx) = c[3]
            raw.append(self.pats[pid])
            c = self.memo[child][idx]
        med_idx = self.mats.index('医疗物资') if '医疗物资' in self.mats else None
        raw.sort(key=lambda p: (-p['n'][med_idx] if med_idx is not None else 0, -p['mass']))
        pools = {m: boxes[(boxes.area == self.area) & (boxes.mat == m)].sort_values(['first', 'box'], ascending=[False, True]).box.tolist() for m in self.mats}
        out = []
        for (number, pt) in enumerate(raw, 1):
            ids = []
            for (mat, n) in zip(self.mats, pt['n']):
                ids += [pools[mat].pop(0) for _ in range(n)]
            p = uav.loc[pt['g']]
            out.append(dict(area=self.area, sortie=number, g=pt['g'], boxes=ids, n=pt['nbox'], mass=pt['mass'], vol=pt['vol'], mass_util=pt['mass'] / qmax_df.loc[self.area, pt['g']], vol_util=pt['vol'] / p.V, first_boxes=sum(boxes.set_index('box').loc[ids, 'first']), E=pt['E'], E_parts=sortie_energy_parts(p, self.geom, pt['mass']), T=pt['T'], T_fly=sortie_flight_time(p, self.geom)))
        return out

def pick(front, rule='NET', ideal=None, w=(1 / 3, 1 / 3, 1 / 3)):
    if not front:
        return None
    if rule == 'W':
        return min(front, key=lambda c: sum((w[k] * c[k] / max(ideal[k], 1e-12) for k in range(3))))
    order = ['NET'.index(x) for x in rule]
    return min(front, key=lambda c: tuple((round(c[k],8) for k in order)))

def global_front(fronts):
    acc = [(0, 0.0, 0.0, None)]
    for fr in fronts:
        if not fr:
            return []
        acc = pareto_filter([(a[0] + b[0], a[1] + b[1], a[2] + b[2], None) for a in acc for b in fr])
    return acc

def solve_all(qmax_df, allowed=None):
    return {a: AreaBatching(a, qmax_df.loc[a], allowed) for a in AREA_IDS}
# Count compression is exact only when each material class has uniform attributes.
assert boxes.groupby(['area','mat'])[['mass','vol']].nunique().le(1).all().all()
assert np.isfinite(seg_df.select_dtypes('number')).all().all()
assert (boxes[['mass','vol']]>0).all().all()
