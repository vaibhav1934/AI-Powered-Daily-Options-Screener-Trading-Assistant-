import os

layers = [
    (1, 'Price Action', 'layer_01_price_action.py', 'Layer01PriceAction'),
    (2, 'Volume/Flow', 'layer_02_volume_flow.py', 'Layer02VolumeFlow'),
    (3, 'Volatility', 'layer_03_volatility.py', 'Layer03Volatility'),
    (4, 'Earnings Calendar', 'layer_04_earnings.py', 'Layer04Earnings'),
    (5, 'Analyst/Sentiment', 'layer_05_analyst.py', 'Layer05Analyst'),
    (6, 'Macro/Rates', 'layer_06_macro_rates.py', 'Layer06MacroRates'),
    (7, 'Sector Rotation', 'layer_07_sector_rotation.py', 'Layer07SectorRotation'),
    (8, 'News/Catalyst', 'layer_08_news_catalyst.py', 'Layer08NewsCatalyst'),
    (9, 'Risk Rules', 'layer_09_risk_rules.py', 'Layer09RiskRules'),
    (10, 'Position Fit', 'layer_10_position_fit.py', 'Layer10PositionFit'),
]

template = '''"""
Layer {num} - {name}
===========================
"""

from __future__ import annotations

from app.framework.factors.base import BaseFactor, ScanContext
from app.framework.layers.base import BaseLayer

class {cls_name}(BaseLayer):
    layer_number = {num}
    name = "{name}"
    description = "Evaluates factors for {name}"

    def get_factors(self) -> list[BaseFactor]:
        from app.framework.factors.registry import factor_registry
        return factor_registry.get_factors_for_layer(self.layer_number)
'''

for num, name, file_name, cls_name in layers:
    path = os.path.join(r'C:\Users\niveus\Project1\backend\app\framework\layers', file_name)
    content = template.format(num=num, name=name, cls_name=cls_name)
    
    if num == 9:
        content += '''
    def process(self, ctx: ScanContext) -> ScanContext:
        """Calculate conviction score before F40 uses it."""
        from app.framework.scoring import calculate_conviction_score
        ctx.conviction_score = calculate_conviction_score(ctx)
        return super().process(ctx)
'''
    elif num == 10:
        content += '''
    def process(self, ctx: ScanContext) -> ScanContext:
        """Final output layer."""
        return super().process(ctx)
'''
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)
