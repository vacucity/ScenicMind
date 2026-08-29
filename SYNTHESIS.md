# 景点游客预测现成模型研究

STATUS: final

## 结论

本文默认目标是“单个景点每日实际入园人数”。该项目不需要从零发明预测方法：季节朴素、ETS、ARIMA/SARIMAX、梯度提升树及 LSTM、N-BEATS/N-HiTS、TFT 等模型族均有成熟理论；其中多种模型已有景点入园人数实证，主流模型也有可集成的软件实现[1–7,9–19]。但“有现成模型”只意味着可以用于系统开发和本地评测，不意味着无需验证即可上线；旅游预测研究反复表明，不存在适用于所有景点、频率和预测时距的单一最优模型[1–3,6,15]。2026 年第二届旅游预测竞赛的综述进一步表明，组合或集成框架通常优于单一模型，合理加入解释性指标能够提升预测精度[15]。

## 可用于开发的模型

| 方法 | 适合场景 | 数据 | 实现路径 |
|---|---|---|---|
| 季节朴素 | 必备基线 | 仅历史客流 | StatsForecast |
| ETS | 单景点、数据较少、稳定季节性 | 历史客流 | StatsForecast AutoETS |
| 动态回归/SARIMAX | 节假日、天气、预约量等外生变量 | 历史入园人数+预测时可知特征 | statsmodels SARIMAX；或 StatsForecast AutoARIMA 自动选阶并加入外生变量 |
| LightGBM | 日入园人数首版主力；非线性、节假日峰值、多景点共享训练 | 滞后/滚动统计+日历+天气/预约 | MLForecast 生成特征并组织全局训练，LightGBM 负责回归 |
| 神经网络候选 | 多景点共享训练且历史较长，重点评测 7–30 天预测 | 多景点日频面板+训练算力 | NeuralForecast 中分别评测 N-BEATS/N-HiTS、TFT 或 LSTM |
| 计数模型 | 低计数、过度离散或零值机制明显 | 历史计数、显式滞后项+可选外生变量 | statsmodels 做含滞后特征的 Poisson/负二项/零膨胀回归；R 的 tscount 做原生 INGARCH 时间序列 |
| 层级协调 | 同时输出景点、片区与总量且必须相加一致 | 各层级序列和基础预测 | HierarchicalForecast |

## 首版推荐

首版推荐同时训练并回测四类候选：季节朴素基线、AutoETS、带节假日/天气预报/预约特征的 SARIMAX，以及带滞后与日历特征的 LightGBM[3,7,9–10]。还应加入简单平均或按验证集加权的模型集成作为对照[15]。LightGBM 可作为首版工程主力，但最终仍以回测结果为准。

如果至少有多个景点可共享训练、每个景点约有两年以上日数据，并且团队具备训练算力与模型监控能力，则应从第一轮评测加入 LSTM、N-BEATS/N-HiTS 或 TFT 中的一种；重点预测 7–30 天时优先级更高。若只有单景点短历史，或缺少相应算力与 MLOps 能力，则不把神经模型列为首版必测项。近三年景点级研究表明，N-BEATS、Tsformer、改进 Informer 和分解式 ConvLSTM 在部分日频、中长期及 15 分钟级任务上优于论文设置的基线模型[5,16,18–19]。但这些研究大多仍采用固定切分，不能替代本项目的滚动回测。

软件上可采用 Python 栈：StatsForecast 2.1.1、statsmodels、MLForecast 1.1.0 和 LightGBM 4.7.0；神经模型按需加入 NeuralForecast 3.2.1，层级总量一致时加入 HierarchicalForecast 1.5.1。这些是 2026-08-28 核验时的版本；各组件采用 Apache-2.0、BSD-3-Clause 或 MIT 许可，落地时应从官方包索引和许可证页重新确认并锁定版本[9–14]。注意 StatsForecast 的外生变量支持取决于具体模型：AutoARIMA 支持，AutoETS 和 SeasonalNaive 不支持；外生变量较多时应使用 SARIMAX、MLForecast 或 NeuralForecast。

## 数据条件

最低数据包括：景点 ID、日期、实际入园人数、开放/闭园状态。强烈建议增加星期几、法定节假日及调休标记、假期所处日次、预测时点已有的预约/预售量、天气预报、活动信息和限流容量。若能够稳定获取，还可加入搜索指数和短视频热度、传播量等外生特征；2024 年的景点级研究显示，短视频信息能够补充传统搜索数据，但收益依赖景点层级和预测时距[17]。只能使用预测发出时已经知道的信息，不能把未来实际天气或目标日最终预约量混入特征[7]。

## 验证方法

采用滚动预测原点回测，不随机打乱数据；按真实业务时距分别评估次日、7 日、14 日或 30 日[7]。至少报告 MAE、RMSE、MASE 和 WAPE；存在闭园或零入园人数时，不要把 MAPE 作为主指标[8]。上线前应预先约定准入规则，例如：候选模型在至少 70% 的滚动窗口中优于季节朴素，核心时距的整体 MASE 更低，且相对 ETS/SARIMAX 的改进达到业务设定的最低收益。这里的 70% 是项目建议阈值，不是文献中的通用定律，可按误判成本调整。

## 局限与条件分支

- 小景点日均入园人数较低、零值频繁，或诊断显示方差明显高于均值：先检验过度离散、零膨胀和序列相关，再选择含滞后特征的 Poisson/负二项/零膨胀回归，或原生 INGARCH；普通计数回归本身不会自动建模序列相关。
- 系统同时输出景点、片区和总游客量：加入层级预测协调。
- 要预测小时或 15 分钟级入园人数、在园人数或拥挤程度：单独建设日内管线，先明确预测目标；不能把日客流模型简单缩短采样间隔后直接复用。
- 时间序列基础模型（Chronos/TimesFM 等）：可作零样本对照，不宜作为首版核心依赖。

## 近三年研究更新（2024–2026）

- **Xu 等（2024）**：使用九寨沟和四姑娘山官方日客流，验证 N-BEATS 在 1–30 天预测中的适用性[5]。
- **Hu、Dong 与 Hu（2024）**：把短视频热度和宣传信息用于旅游需求预测，四姑娘山案例表明新型社媒数据可作为外生特征[17]。
- **Yi、Chen 与 Tang（2025）**：在公开的九寨沟、四姑娘山数据上比较 Tsformer 与 9 个基线，覆盖 1、7、15、30 天预测；数据可用于本项目复现实验[16]。
- **李新等（2025）**：使用北京 7 个 5A 景区每 15 分钟客流，对 Informer、Autoformer、Fedformer、DeepAR、TCN、LSTM、GBRT 和 ARIMA 进行比较，补足日内高频场景证据[18]。
- **Zhan 等（2026）**：在九寨沟长期日客流上研究季节趋势分解与 ConvLSTM-Attention，说明分解式神经模型有助于高峰客流捕捉，但全样本上相对部分基线的优势并非都显著[19]。
- **Song、Li 与 Wu（2026）**：第二届旅游预测竞赛综述基于 24 支队伍的事前预测结果，支持“组合/集成优于单一模型”和“必须进行真实样本外验证”的判断[15]。该研究是旅游目的地层级证据，不是单景点闸机客流证据。

## 参考文献

1. Song, H., & Li, G. (2008). Tourism demand modelling and forecasting—A review of recent research. Tourism Management, 29(2), 203–220. https://doi.org/10.1016/j.tourman.2007.07.016
2. Song, H., Qiu, R. T. R., & Park, J. (2019). A review of research on tourism demand forecasting. Annals of Tourism Research, 75, 338–362. https://doi.org/10.1016/j.annals.2018.12.001
3. Athanasopoulos, G., Hyndman, R. J., Song, H., & Wu, D. C. (2011). The tourism forecasting competition. International Journal of Forecasting, 27(3), 822–844. https://doi.org/10.1016/j.ijforecast.2010.04.009
4. Bi, J.-W., Liu, Y., & Li, H. (2020). Daily tourism volume forecasting for tourist attractions. Annals of Tourism Research, 83, 102923. https://doi.org/10.1016/j.annals.2020.102923
5. Xu, K., Zhang, J., Huang, J., Tan, H., Jing, X., & Zheng, T. (2024). Forecasting Visitor Arrivals at Tourist Attractions: A Time Series Framework with the N-BEATS. Sustainability, 16(18), 8227. https://doi.org/10.3390/su16188227
6. Volchek, K., Liu, A., Song, H., & Buhalis, D. (2019). Forecasting tourist arrivals at attractions: Search engine empowered methodologies. Tourism Economics, 25(3), 425–447. https://doi.org/10.1177/1354816618811558
7. Hyndman, R. J., & Athanasopoulos, G. (2021). Forecasting: Principles and Practice (3rd ed.). https://otexts.com/fpp3/
8. Hyndman, R. J., & Koehler, A. B. (2006). Another look at measures of forecast accuracy. International Journal of Forecasting, 22(4), 679–688. https://doi.org/10.1016/j.ijforecast.2006.03.001
9. StatsForecast official documentation and package metadata. https://nixtlaverse.nixtla.io/statsforecast/ ; https://pypi.org/project/statsforecast/ (accessed 2026-08-28).
10. MLForecast official documentation and package metadata. https://nixtlaverse.nixtla.io/mlforecast/ ; https://pypi.org/project/mlforecast/ (accessed 2026-08-28).
11. statsmodels official documentation and package metadata. https://www.statsmodels.org/stable/ ; https://pypi.org/project/statsmodels/ (accessed 2026-08-28).
12. LightGBM official documentation and package metadata. https://lightgbm.readthedocs.io/en/latest/ ; https://pypi.org/project/lightgbm/ (accessed 2026-08-28).
13. NeuralForecast official documentation and package metadata. https://nixtlaverse.nixtla.io/neuralforecast/ ; https://pypi.org/project/neuralforecast/ (accessed 2026-08-28).
14. HierarchicalForecast official documentation and package metadata. https://nixtlaverse.nixtla.io/hierarchicalforecast/ ; https://pypi.org/project/hierarchicalforecast/ (accessed 2026-08-28).
15. Song, H., Li, G., & Wu, D. C. (2026). A review of the second tourism forecasting competition for post-pandemic recovery. Annals of Tourism Research, 119, 104207. https://doi.org/10.1016/j.annals.2026.104207
16. Yi, S., Chen, X., & Tang, C. (2025). Time series transformer for tourism demand forecasting. Scientific Reports, 15, 29565. https://doi.org/10.1038/s41598-025-15286-0
17. Hu, M., Dong, N., & Hu, F. (2024). Tourism demand forecasting using short video information. Annals of Tourism Research, 109, 103838. https://doi.org/10.1016/j.annals.2024.103838
18. 李新, 张旭, 余乐安, 汪寿阳. (2025). 基于改进Transformer模型的景区短时客流预测研究. 中国管理科学, 33(2), 105–117. https://doi.org/10.16381/j.cnki.issn1003-207x.2023.1927
19. Zhan, L., Sun, X., Shi, X., & Wu, T. (2026). Tourist Flow Forecasting for Sustainable Scenic Area Management Using a Seasonal Trend Decomposition-Enhanced ConvLSTM Framework. Sustainability, 18(14), 7099. https://doi.org/10.3390/su18147099
