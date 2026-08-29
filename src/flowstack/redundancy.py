"""冗余感知特征选择。

痛点背景：数据集中大量特征是同一维度的重复/高相关变体
（如 visitors_lag_1 / visitors_roll_mean_3 / visitors_roll_mean_7、
weather_temp_mean/max/min_lag1、wiki_zh_views_lag1/ma7 等）。
全部塞入模型不会必然降低树模型精度，但会：
  1. 稀释并随机化特征重要性，破坏对下游 Agent 的可解释输出；
  2. 增加分裂搜索噪声与过拟合风险（多重共线性）；
  3. 拖慢训练。

机制：Spearman 相关聚类（单调关系，比 Pearson 更适合偏态客流特征）
→ 簇内按"与目标的互信息"排序 → 每簇保留 top-k 代表。
仅在训练集上 fit，测试/预测阶段只做 transform，无泄漏。
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from src.flowstack.config import RedundancyConfig


@dataclass
class FeatureCluster:
    representative: str
    members: list[str]
    mi_scores: dict[str, float] = field(default_factory=dict)


class RedundancyReducer:
    """相关性聚类 + 簇内代表特征选择。"""

    def __init__(self, config: RedundancyConfig):
        self.config = config
        self.clusters: list[FeatureCluster] = []
        self.selected_features_: list[str] = []
        self.dropped_features_: list[str] = []

    def fit(self, x: pd.DataFrame, y: pd.Series) -> "RedundancyReducer":
        from sklearn.feature_selection import mutual_info_regression

        columns = list(x.columns)
        if not self.config.enabled or len(columns) <= 1:
            self.selected_features_ = columns
            self.clusters = [FeatureCluster(c, [c]) for c in columns]
            return self

        # 1) 互信息打分（与目标的相关强度，捕捉非线性）
        mi = mutual_info_regression(
            x.to_numpy(dtype=float), y.to_numpy(dtype=float),
            random_state=0, n_neighbors=3,
        )
        mi_score = dict(zip(columns, mi))

        # 2) Spearman 相关矩阵（对单调冗余稳健）；常量列相关为 NaN，按 0 处理
        corr = x.corr(method="spearman").abs().to_numpy()
        corr = np.nan_to_num(corr, nan=0.0)
        np.fill_diagonal(corr, 1.0)
        threshold = self.config.corr_threshold

        # 3) 按互信息降序贪心聚类：高价值特征优先成为簇代表，
        #    吸收所有与其 |rho| >= threshold 的未归属特征（单链吸收）。
        order = sorted(columns, key=lambda c: -mi_score[c])
        assigned: set[str] = set()
        idx = {c: i for i, c in enumerate(columns)}
        clusters: list[FeatureCluster] = []
        for rep in order:
            if rep in assigned:
                continue
            members = [
                c for c in columns
                if c not in assigned and corr[idx[rep], idx[c]] >= threshold
            ]
            members.sort(key=lambda c: -mi_score[c])
            for c in members:
                assigned.add(c)
            keep = members[: max(1, self.config.max_per_cluster)]
            clusters.append(
                FeatureCluster(
                    representative=keep[0],
                    members=members,
                    mi_scores={c: round(float(mi_score[c]), 6) for c in members},
                )
            )

        self.clusters = clusters
        self.selected_features_ = [c.representative for c in clusters]
        kept = set(self.selected_features_)
        self.dropped_features_ = [c for c in columns if c not in kept]
        return self

    def transform(self, x: pd.DataFrame) -> pd.DataFrame:
        missing = [c for c in self.selected_features_ if c not in x.columns]
        if missing:
            raise ValueError(f"预测输入缺少代表特征: {missing}")
        return x.loc[:, self.selected_features_]

    def fit_transform(self, x: pd.DataFrame, y: pd.Series) -> pd.DataFrame:
        return self.fit(x, y).transform(x)

    def cluster_of(self, feature: str) -> FeatureCluster | None:
        for cluster in self.clusters:
            if feature in cluster.members:
                return cluster
        return None

    def report(self) -> pd.DataFrame:
        """冗余簇报告：供 Agent 理解"代表特征 ↔ 被合并特征"的映射。"""
        rows = []
        for cluster in self.clusters:
            rows.append(
                {
                    "representative": cluster.representative,
                    "cluster_size": len(cluster.members),
                    "members": "|".join(cluster.members),
                    "dropped": "|".join(
                        m for m in cluster.members if m != cluster.representative
                    ),
                    "representative_mi": cluster.mi_scores.get(cluster.representative, 0.0),
                }
            )
        return pd.DataFrame(rows).sort_values(
            ["cluster_size", "representative_mi"], ascending=False
        ).reset_index(drop=True)
