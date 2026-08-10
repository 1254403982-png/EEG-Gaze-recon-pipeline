window.questionBank = window.questionBank || {};
window.questionBank.easy = window.questionBank.easy || [];
window.questionBank.easy.push(
  { id:12, title:"理想气体状态方程与气体定律", domain:"物理", difficulty:"低", diffClass:"is-low",
    summary:"理想气体状态方程PV=nRT统一描述气体的压强、体积、温度和物质量之间的关系，三大气体定律是其特例。",
    quickQs:["理想气体的两大假设","波义耳定律在日常生活中的例子","给我出道练习题","用通俗语言解释"],
    content:`<p>气球受热会膨胀、高压锅做饭更快、潜水员上浮太快会得"减压病"——这些都跟气体的宏观性质有关。物理学用一个简洁的方程把它们统一起来：<strong>理想气体状态方程 PV = nRT</strong>。</p>
<h3>理想气体模型的两个假设</h3>
<p>真实气体分子有大小、分子之间有作用力。但当气体足够稀薄（低压高温）时，可以忽略这两点，抽象出<strong>理想气体</strong>模型：①气体分子本身没有体积（视为质点）；②分子之间除碰撞外没有相互作用力。在这个模型下，一切变得简单优美。</p>
<h3>状态方程与三大气体定律</h3>
<div class="formula-block"><span class="formula-label">理想气体状态方程</span>PV = nRT<br>P=压强(Pa), V=体积(m³), n=物质的量(mol)<br>T=绝对温度(K), R=8.314 J/(mol·K)（普适气体常数）</div>
<p>这个方程包含了三个著名的实验定律作为特例：</p>
<table class="data-table">
<tr><th>定律名</th><th>固定条件</th><th>关系式</th><th>一句话理解</th></tr>
<tr><td>波义耳定律</td><td>T、n不变</td><td>P₁V₁=P₂V₂</td><td>恒温下：压强↑体积↓（挤压气球）</td></tr>
<tr><td>查理定律</td><td>P、n不变</td><td>V₁/T₁=V₂/T₂</td><td>恒压下：温度↑体积↑（热气球升空）</td></tr>
<tr><td>盖-吕萨克</td><td>V、n不变</td><td>P₁/T₁=P₂/T₂</td><td>恒容下：温度↑压强↑（高压锅原理）</td></tr>
</table>
<h3>应用实例</h3>
<p>高压锅就是利用查理/盖-吕萨克定律：密封加热使内部气压升高至约2个大气压，水的沸点从100°C升至约120°C，食物熟得更快。潜水员上浮过快时，溶解在血液中的氮气因压强骤降而析出形成气泡——这就是减压病的物理原因，需要缓慢上浮让气体逐步排出。</p>
<h3>理想气体与真实气体</h3>
<p>理想气体模型在高压或低温下会失效——此时分子体积和分子间引力不可忽略。为修正这一点，范德华用两个参数改进了方程：</p>
<div class="formula-block"><span class="formula-label">范德华方程（1 mol）</span>$$(P + \\frac{a}{V^2})(V - b) = RT$$<br>a 修正分子间引力，b 修正分子本身体积</div>
<p>当 a=b=0 时，它就退化回理想气体状态方程。范德华方程能定性解释气体的液化、临界点等现象，是连接理想模型与真实世界的一座桥梁。</p>`,
    quiz:[{ question:"一定量的理想气体在恒温下体积压缩为原来的一半，压强变为原来的几倍？", options:["A. 1倍(不变)","B. 2倍","C. 1/2倍","D. 4倍"], answerIndex:1 },
           { question:"高压锅内食物熟得更快的根本原因是？", options:["A. 锅内气压更高使水的沸点升高","B. 金属导热更好","C. 加热功率更大","D. 减少了热量散失"], answerIndex:0 }] }
);
