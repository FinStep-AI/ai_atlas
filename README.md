# ai_atlas

## 公司名称配色逻辑

图谱中公司名称标签的颜色用于区分公司的市场 / 上市地属性，不代表公司重要性、推荐程度或产业地位高低。

当前配色逻辑基于 `company_nodes.csv` 中的 `market` 字段判断。

| 样式颜色 | 示例 | 判断条件 | 含义 |
| --- | --- | --- | --- |
| 紫色 | 昆仑万维 | `market` 包含 `科创` 或 `创业` | 科创板 / 创业板等成长型科技公司 |
| 蓝色 | Anthropic | `market` 包含 `外资` 或 `美` | 外资公司、海外公司、美股公司等 |
| 青蓝色 | 港股公司 | `market` 包含 `港` | 港股上市公司 |
| 橙色 | 台股公司 | `market` 包含 `台` | 台股上市公司 |
| 黑色 / 深灰色 | 豪威集团 | 不满足以上条件 | 默认 A 股公司、北交所公司、未明确市场属性公司或其他类型公司 |

代码中的判断优先级为：

```text
外资 / 美股 > 港股 > 台股 > 科创板 / 创业板 > 默认 A 股 / 其他
```

对应逻辑大致为：

```python
market_cls = (
    'market-foreign' if ('外资' in market or '美' in market)
    else 'market-hk' if '港' in market
    else 'market-tw' if '台' in market
    else 'market-growth' if ('科创' in market or '创业' in market)
    else 'market-a'
)
```

因此，同一家公司显示为什么颜色，主要取决于其 `market` 字段内容。
