# 问题一优化版：时间优先决策与论文图表

本目录对应第六章，覆盖最大安全载荷、不可拆货箱组批、三指标权衡、返航安全余量敏感性四项任务。正式输入来自项目 `26-Modeling/001-Issue/D题/`，原始 `002-Code/Q1.ipynb` 保留不变。

## 本次实质变化

- 保留并核验原 Notebook 的附录物理模型、装载模式与 Pareto 动态规划。提取为本目录 `model.py`，不引入无必要的复杂算法。
- R3（T→N→E）为推荐规则；机型集合比较与敏感性结果统一采用该规则，并保留 R1/R2/R4 对照。时间指累计作业投入，不是配送及时性或多机并行完工时间。
- 两个前沿点仅在 S008 不同：一架 C（45 kg）与两架 B（25+20 kg）。明确代价、相对变化、完整权重切换不等式与 epsilon 时间容忍门槛。
- 增加单箱可行性充要条件，解析得到完整配送上界 35.26780661%，不将网格最大可行点35%当作真正边界。
- 不可完整配送时，全局三指标记缺失，避免用部分配送合计冒充完成全部任务。
- 同类箱属性一致性有断言；字典序使用小数点后8位比较以消除浮点求和尾差的假优先；支配比较容差为1e-9。
- 重绘9幅图，包含真实DEM三维图、三指标决策图、局部替换和失效边界图。未使用生成式图像、模拟绩效或虚构误差条。

## 主要结果

| 方案 | N | E (kWh) | T (h) |
|---|---:|---:|---:|
| 时间优先P_T（R1/R3/R4同点） | 18 | 59.131296 | 9.104449 |
| 能耗优先P_E（R2） | 19 | 59.033943 | 9.566660 |

推荐方案B型9架次、C型9架次，80箱全部唯一分配。选择能耗优先仅节省0.097354 kWh，却增加1架次与27.732694分钟累计时间。权重截面wN=wT时，理想点归一化下wE超过0.969912497才改选P_E；这不是通用权重建议。没有宣称数值上优于原有精确解。

## 运行

已核验 Python 3.10.21（项目py310）、NumPy、pandas、SciPy、Matplotlib、openpyxl；PDF质检另外使用PyMuPDF（本轮已安装）。Notebook用nbformat/nbclient和py310内核。未修改全局Conda配置。

从本目录依次执行（`python` 指向项目py310）：

```bash
python analyze.py
python verify.py
python plot_figures.py
python qa_figures.py
python export_tables.py
```

`Q1_optimized.ipynb` 提供同一流程的Notebook入口及结果展示，不维护另一套求解逻辑。`figure_backend.json` 仅保存本任务Python选择，不改动其他项目。

进入 `../Q1-latex/` 后执行：

```bash
latexmk -xelatex -interaction=nonstopmode -halt-on-error -outdir=build Q1.tex
```

入口按用户指定使用 `bwprint,fontset=windows` 及完整导言，已通过本机字体编译。模型程序自行按文件位置定位项目根目录；原始附件不复制、不修改。全部计算确定性，无需随机种子。`analyze.py` 基准+扫描运行约数秒，绘图和PDF编译时间另计。

## 输出与可追溯关系

- `results/qmax.csv`、`binding.csv`、`geometry.csv`：45项载荷、限制来源和15条航段几何。
- `results/plans.json`、`plan_R1.csv`至`plan_R4.csv`：完整逐箱ID和逐架次代价；箱号属于原始清单，非新造编号。
- `results/front.csv`、`rules.csv`、`policies.csv`、`summary.json`：三目标前沿、决策与机型比较、归一化和解析边界。
- `results/sensitivity*.csv`：41个余量水平，三种优先规则；全45组合载荷和逐区推荐架次数。
- `results/singleton_boundaries.csv`：每箱每种可用机型的临界余量；全局临界货箱为S008两箱饮用水。
- `results/milp_checks.csv`、`constraint_checks.csv`、`geometry_checks.csv`、`payload_root_checks.csv`、`verification.json`：独立检查证据。
- `figure_plan.md`：任务—论点—证据—图件清单与统一术语。
- `qa/`：面板几何、PDF文字字号、碰撞、源代码审核、论文逐页预览与人工复核记录。
- `../Q1-latex/figures/`：9幅图，PDF为论文引用版本，PNG为300dpi预览，SVG保留可编辑文字。
- `../Q1-latex/tables/`：5张由结果自动生成的三线表。
- `../Q1-latex/Q1.tex`：独立编译入口；`chapter.tex`：可并入全文的第六章正文；`build/Q1.pdf`：章节预览。

## 验证与限制

15条航段用独立像元边界交点法复核；45个载荷用Brent求根复核；629个非零DP状态用两两支配判定复查；45项单目标最优值用未剪枝装载模式整数规划核验，并核验每个局部前沿点在N/T上界内的最低能耗。四条规则的方案均从原始箱号独立重算载质量、体积、能耗、时间和唯一覆盖。临界余量上下1e-6重新求解验证可行性变化。

精确性仅限本题指定物理规则、数据与有限装载模式，允许数值容差及同目标解合并，不等于实飞验证。图中地形以4×4像元块最大值聚合显示，计算仍使用原始DEM；三维高度方向夸张且航线前置叠加，不作为精密净空判读，需结合原分辨率几何检查和剖面。

主文集中呈现四项任务结果、S008冲突和失效边界；全部箱号、扫描与验证细节留结果文件。删除原Notebook中“多规则同点即无冲突”、以问题二资源占用推导本问首选、以及未经核验的指数物理来源表述。字体重定义和hyperref固定选项提示来自原类文件，不修改模板；具体编译及图件质检记录见qa。

## 并入全文

将`chapter.tex`正文作为第六个section，删除独立入口中的section计数器设置。图件和tables按相应路径复制/同步后再编译；如主文统一采用`figures/Q1/`，需批量调整本章图片路径并同步表格input路径。标签均以q1限定。全篇已有图表/公式计数器规则可能影响最终编号，应在合并后复查交叉引用。暂未改写第1–5章、问题二至四或已有初稿。
