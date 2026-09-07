# DataMind — 公募基金定期报告智能分析

从基金定期报告（XBRL/XML/HTML 页面/PDF）一键完成：**数据抓取 → 11 表标准化提取 → 4 维分析 → Excel/Markdown 报告输出**，并提供带历史记录管理与横向对比的 Web 界面。

## 功能总览

**分析管线（CLI / Web 共用）**
- 解析 XBRL 实例 XML（生产级）、PDF 文本（兜底）、CSRC 报告 HTML 页面
- 11 表标准化提取（基本信息 / 财务指标 / 净值表现 / 资产负债 / 利润 / 净资产变动 / 投资组合 / 前十大持仓 / 行业配置 / 持有人结构 / 新发募集），缺失字段显式标记 `missingb`，不编造数值
- 4 维分析：
  - 维度1：管理规模（规模趋势、同公司对比、规模排名、集中度、变动归因）
  - 维度2：业绩表现（分阶段收益率、超额收益、收益-风险、同类排名、累计走势）
  - 维度3：资产配置（大类资产、行业分布、前十大持仓及集中度、债券品种）
  - 维度4：竞品对标（头部公司规模、同类业绩雷达、风格散点、规模-业绩矩阵、季度追踪）
- Excel 报告自动生成图表（折线/柱状/饼图/雷达/散点/气泡）

**Web 门户**（`web_portal.py`，端口 8787）
- 输入报告 URL 或上传 XML/XBRL → 一次生成抓取数据 + 4 维分析
- 双层预览：第一层 11 表抓取数据；第二层 4 维分析 + 图表
- 分析历史侧边栏：回看、单条删除、勾选批量删除（均带确认）
- 勾选 ≥2 条横向对比，6 个对比方向（基金规模对比 / 规模排名 / 各阶段收益率 / 超额收益 / 收益-风险评估 / 同类业绩排名）

## 快速开始

### 方式一：下载exe（免装Python）

从 [Releases](../../releases) 下载 `DataMind-vX.X.X-windows-x64.exe`，双击运行后访问 <http://127.0.0.1:8787>。分析结果保存在 exe 同级的 `output/web_runs/` 目录。

### 方式二：从源码运行

要求 Python 3.11+。

```bash
git clone <your-repo-url> datamind
cd datamind
pip install -r requirements.txt
python web_portal.py
```

打开 <http://127.0.0.1:8787>。

### 手机 / iPad 访问（同一局域网）

Web 界面自带响应式布局与 `viewport` 配置，iPhone / iPad 浏览器可直接使用（需电脑保持开机运行服务）：

```bash
python web_portal.py --host 0.0.0.0
```

然后在手机浏览器访问 `http://<电脑局域网IP>:8787`（`ipconfig` 查看 IPv4 地址，如 `192.168.1.100:8787`）。首次运行 Windows 防火墙弹窗请选择"允许"；打包版 exe 同样支持 `DataMind.exe --host 0.0.0.0`。默认不开启局域网访问，仅本机使用时无需任何改动。

### 命令行

```bash
# 样例数据
python app.py --input data/sample_xbrl

# 直接分析报告 URL
python app.py --input-url "http://eid.csrc.gov.cn/xbrl/REPORT/HTML/..."

# 按清单批量下载后分析
python app.py --download-manifest data/sample_manifest.csv --download-dir data/downloaded_xbrl

# 自定义输出与基金过滤
python app.py --input path/to/xbrl_folder --output output/report.xlsx --funds "华夏成长精选A,博时稳定债券C"
```

输出：`output/fund_competitor_report.xlsx` + `output/fund_competitor_report.md`。

## 测试

```bash
pip install -r requirements-dev.txt
pytest tests -v
```

测试覆盖：端到端管线（11 表生成、missingb 标记）、4 维分析工作簿（工作表结构、图表数量）、Web 全部路由（上传/回看/对比/单条与批量删除/路径穿越防护）。

## 打包 Windows exe

```bash
build_exe.bat
```

产物：`dist/DataMind.exe`（单文件，内嵌模板与静态资源，输出目录定位在 exe 同级）。

## 发版流程

推送 `v*` 格式的 tag（如 `v1.0.0`）后，GitHub Actions 自动：跑全量测试 → PyInstaller 构建 Windows x64 exe → 创建 Release 并附上 exe。详见 `.github/workflows/release.yml`。

## 项目结构

```
app.py                    CLI 入口
web_portal.py             Web 门户入口（Flask）
web_app.py                桌面 UI 入口（Tkinter）
build_exe.bat             PyInstaller 打包脚本
src/datamind/
  pipeline.py             端到端编排
  xbrl_parser.py          XBRL 解析（contextRef 维度拆分 A/C 份额）
  html_parser.py          CSRC 报告 HTML 抓取
  pdf_parser.py           PDF 文本解析（兜底）
  cleaning.py             清洗与标准化
  selected_analysis.py    11 表选择提取 + 4 维分析模板
  comparison.py           多 run 横向对比
  reporting.py            Excel/Markdown 报告
  downloader.py           URL 清单下载
  config.py               字段/标签别名配置
data/sample_xbrl/         样例数据
tests/                    pytest 测试
.github/workflows/        CI 与 Release 工作流
```

## 说明

- 解析器映射常用标签别名，可在 `src/datamind/config.py` 扩展；XBRL 标签不同时在 `FIELD_TAG_CANDIDATES` 里补充候选标签
- PDF 提取基于文本正则，支持常见中英文字段；特殊模板可调整 `src/datamind/pdf_parser.py`
- 追求稳定与精确的季度对比时，优先使用监管/基金公司 XBRL 实例 XML 而非 PDF
- 本项目仅供个人研究使用，不构成任何投资建议

## License

[MIT](LICENSE)
