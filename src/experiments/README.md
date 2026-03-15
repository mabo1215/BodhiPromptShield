# 实验与消融表

## prior_ablation_table.py

生成论文中 Ablation 表（Table tab:ablation）所需数值。

- **(A) DBN/PB**：来自 prior 论文 [ma2021privacy]（MTAPBoMa）Table 1（MIMIC）与 Fig.9（COVID-19）。脚本内硬编码该表数据，运行后输出 (A) 行的 Train/Val 与 LaTeX 片段。
- **(B)(C)(D)(E)**：若指定 `--reaedp` 指向 `REAEDP/data`，会用该目录下 CSV（如 CDC BRFSS、tabular-feature-engineering）跑一个简单分类基线，输出占位数值；否则输出 `--`。真实消融 (B)--(E) 需用 IBPPSVM 代码在相应配置下跑实验后替换。

**用法**

```bash
# 仅输出 (A) 及 (B)--(E) 占位
python src/experiments/prior_ablation_table.py

# 使用 REAEDP 数据跑占位基线并写出 CSV
python src/experiments/prior_ablation_table.py --reaedp C:/source/REAEDP/data --out ablation_table.csv
```

依赖：无（仅 (A)）；若使用 `--reaedp` 需 `pandas`, `scikit-learn`, `numpy`。
