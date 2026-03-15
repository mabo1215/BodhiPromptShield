# IBPPSVM 论文配套代码

- **`algorithms/`**  
  - `differential_privacy.py`: ε-差分隐私、Laplace 噪声与敏感度（论文中 \(N_{\mathrm{Privacy\ Noise}}\)，无 DBN/PB）。  
  - `gdifsea.py`: GDIFSEA（独立支撑、频繁闭子串、N-GRAM 图），用于 MWU/词典构建。
- **`figures/`**  
  - `doc2vec_distribution.py`: Doc2Vec 高维环分布、χ² 理论分布、边缘分布图。  
  - `category_margin.py`: 分类边界（内部分类中心、ppSVM margin）示意图。  
  - `spatial_internal_categories.py`: 内部分类空间分布 2D 投影。  
  - `run_all_figures.py`: 一键生成上述图并输出到 `paper/fig/`。

**依赖**：`numpy`, `matplotlib`, `scipy`（见 `requirements.txt`）。

**一键运行（推荐）**：在**仓库根目录**执行以下任一方式，会自动创建 `.venv`（若不存在）、激活、安装依赖并运行全部代码（图表生成 + 算法烟雾测试）：
- **PowerShell**：`.\run_src.ps1`
- **CMD**：`run_src.bat` 或双击 `run_src.bat`

**仅生成图表**：激活虚拟环境后执行  
`python src/run_all.py` 或 `python src/figures/run_all_figures.py --out-dir paper/fig`。
