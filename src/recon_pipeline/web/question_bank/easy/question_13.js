window.questionBank = window.questionBank || {};
window.questionBank.easy = window.questionBank.easy || [];
window.questionBank.easy.push(
  { id:13, title:"酸碱平衡与pH值计算", domain:"化学", difficulty:"低", diffClass:"is-low",
    summary:"pH值衡量溶液的酸碱度，缓冲溶液能抵抗pH的剧烈变化，在生物体内维持酸碱平衡至关重要。",
    quickQs:["pH值的定义和计算","缓冲溶液的工作原理","给我出道练习题","用通俗语言解释"],
    content:`<p>柠檬汁是酸的，肥皂水是碱的——我们凭味觉就能区分。但要精确描述"有多酸"或"有多碱"，就需要一个定量指标：<strong>pH值</strong>。</p>
<h3>pH值：氢离子浓度的"缩放版"</h3>
<p>水溶液中始终存在水自身的电离：H₂O ⇌ H⁺ + OH⁻。酸性溶液中H⁺浓度高，碱性溶液中OH⁻浓度高。由于H⁺浓度变化范围极大（可以从10⁻¹⁴到1 mol/L），直接用数值不方便，于是取以10为底的对数的负值：</p>
<div class="formula-block"><span class="formula-label">pH的定义</span>pH = -log₁₀[H⁺]<br>常温25°C：pH&lt;7 为酸性，pH=7 为中性，pH&gt;7 为碱性<br>注意：pH每减小1，[H⁺]增大10倍！</div>
<h3>缓冲溶液：抵抗pH变化的"海绵"</h3>
<p>纯水中滴入几滴盐酸，pH可能从7骤降到2。但在血液中（pH≈7.4），即使摄入酸性食物或代谢产生大量CO₂，pH的变化却极其微小。这是因为血液是<strong>缓冲溶液</strong>——它含有"共轭酸碱对"（如 H₂CO₃/HCO₃⁻），能中和外来的酸或碱。</p>
<div class="formula-block"><span class="formula-label">亨德森-哈塞尔巴尔赫方程</span>pH = pKa + log([共轭碱]/[共轭酸])<br>当[碱]=[酸]时，pH = pKa（此即缓冲能力的最佳点）</div>
<p>人体血液的缓冲体系（碳酸氢盐缓冲对）可将 pH 稳定在 7.35~7.45 的狭窄范围。超出这个范围（酸中毒或碱中毒）会严重影响酶的活性甚至危及生命——这也是医院急诊首先要查血气分析的原因。</p>
<h3>缓冲的"有效范围"与缓冲对的选择</h3>
<p>缓冲溶液并非无限能扛：它只在 pKa±1 的范围内效果最好，且缓冲对的两边浓度越接近 1:1，缓冲能力越强。血液的碳酸氢盐对 pKa≈6.1，看似与生理 pH 7.4 差得远，但身体靠<strong>肺不断排出 CO₂、肾不断重吸收 HCO₃⁻</strong>，把 [HCO₃⁻]/[H₂CO₃] 维持在约 20:1，从而既偏移了工作点、又获得了巨大的缓冲容量。此外，细胞内还有磷酸盐缓冲对（HPO₄²⁻/H₂PO₄⁻，pKa≈7.2），专门在细胞和尿液中"兜底"。</p>`,
    quiz:[{ question:"某溶液的pH从5降到3，其H⁺浓度变化了多少倍？", options:["A. 2倍","B. 10倍","C. 100倍","D. 1000倍"], answerIndex:2 },
           { question:"人体血液能稳定维持在pH 7.4左右，主要依靠什么机制？", options:["A. 不断排出所有H⁺","B. 缓冲体系的中和作用","C. 肾脏完全过滤掉酸","D. 温度调节"], answerIndex:1 }] }
);
