# Criteo Uplift MVP

目标：在 Criteo 公开随机广告增量实验上，比较“按转化响应概率排序”和
“按增量转化排序”，并在固定定向预算下进行离线策略评估。

当前证据边界（D3 已完成，D4 进行中）：官方 unbiased v2.1 原始数据契约已锁定；
全量数据审计、确定性 70/15/15 split、仅 train 下采样、处理前特征平衡及稀有单元
gate 已真实运行。透明 IPW Gain/Qini/top-k 口径已通过合成手算与回归测试。D3 的
response/S/T-Learner 已在 D2 固定 validation 上完成真实 full-validation 运行
（train=1,957,575 / validation=2,096,612，test 未使用），产出结果表、预测文件与
Qini 曲线；response 当前在 Qini/top-10% gain 上数值最高，但用户已将此限定为
"当前 validation、当前线性模型配置下的观察"，不做普遍性推广。D4 已对该结果做过
一次干净的无 cap 全量重跑，重跑产物与原结果逐字节完全相同。详见
`docs/evidence/D3_ACCEPTANCE.md`。

## D1 快速验证

```bash
cd /Users/hx/dev/work2/causal-uplift-project
python3 scripts/download_criteo.py
python3 scripts/inspect_criteo_d1.py
python3 -m unittest discover -s tests -v
```

预期：验证固定 SHA-256、`13,979,592 × 16` schema、二元字段与实验臂聚合，
生成 `artifacts/d1_criteo_inspection.json`，全部 5 项测试通过。

## 数据来源与许可边界

- 官方页面：<https://ailab.criteo.com/criteo-uplift-prediction-dataset/>
- 官方 unbiased v2.1 文件由 `scripts/download_criteo.py` 获取。
- 数据许可：发布方页面列明 CC BY-NC-SA 4.0。
- 本地原始文件：`data/raw/criteo-uplift-v2.1.csv.gz`，不提交到 Git。
- 本地固定 SHA-256：
  `2716e1bf0fd157a93b5bf86924d9088419dfbac2022c6cd90030220634f616dc`。
- 原始文件和派生数据均由 `.gitignore` 排除；仓库仅保存来源、归属、下载/
  校验代码和聚合证据。

项目契约见 `docs/project_contract.md`，来源证据见
`docs/criteo_source_record.md`，当前验收见
`docs/evidence/D1_CRITEO_ACCEPTANCE.md`。

D1 的实际学习范围、分任务通过状态和证据入口见
`docs/day1_packet.md`。数据切换前的 Hillstrom 日包已明确归档为
`docs/day1_packet_hillstrom_legacy.md`，不代表用户已学习其中专属内容。

D2 的真实审计/split、指标约定、用户 ownership 和未完成边界见
`docs/evidence/D2_ACCEPTANCE.md`。

D1→D2→D3 的全局位置、D2 概念图表、手算例、真实审计结果和复习卡见
`docs/day2_packet.md`。

D3 的 learner 公式、手算、门控命令、输出不变量、常见错误和验收格式见
`docs/day3_packet.md`。真实 Criteo 模型命令必须在第一个 user-owned 契约检查通过后
运行；D3 只使用 validation，test 留给 D4 冻结后评估。

D3 的真实 full-validation 结果、结果解读边界、意外结果的分布诊断、可复现性
运行步骤、seed/split 契约、artifact 索引和实验日志见
`docs/evidence/D3_ACCEPTANCE.md`。test 集截至该文档记录时仍未被使用。

## Hillstrom 回退

此前的 Hillstrom 原始数据、检查器、测试和聚合 JSON 均原样保留，契约副本
位于 `docs/hillstrom_fallback_contract.md`。它只在 Criteo 超出技术风险门槛
时启用，不作为并行建模分支。
