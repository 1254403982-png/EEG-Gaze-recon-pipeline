window.questionBank = window.questionBank || {};
window.questionBank.hard = window.questionBank.hard || [];
window.questionBank.hard.push(
  { id:44, title:"热力学势与相变理论", domain:"物理", difficulty:"高", diffClass:"is-high",
    summary:"四种热力学势分别适用于不同约束条件，吉布斯自由能在等温等压下判定反应自发方向，相变体现为势函数的突变。",
    quickQs:["四种热力学势的含义","相变的热力学条件","给我出道练习题","用通俗语言解释"],
    content:`<p>判断一个过程"会不会自发发生"，不同条件下要用不同的"标尺"。<strong>热力学势</strong>就是一组状态函数，分别对应不同的约束（温度、压强、体积），帮我们快速判断平衡与方向。</p>
<h3>四种热力学势</h3>
<table class="data-table">
<tr><th>势函数</th><th>定义</th><th>自然变量</th><th>适用场景</th></tr>
<tr><td>内能 U</td><td>系统所有能量总和</td><td>S, V</td><td>孤立系统（熵最大）</td></tr>
<tr><td>焓 H</td><td>H = U + pV</td><td>S, p</td><td>等压过程（ΔH=热量）</td></tr>
<tr><td>亥姆霍兹自由能 A</td><td>A = U - TS</td><td>T, V</td><td>等温等容</td></tr>
<tr><td>吉布斯自由能 G</td><td>G = H - TS</td><td>T, p</td><td>等温等压（化学/生物）</td></tr>
</table>
<h3>极值原理：平衡时势函数取极值</h3>
<div class="formula-block"><span class="formula-label">极值原理</span>孤立系统：ΔS ≥ 0（熵最大）<br>等温等压：ΔG ≤ 0（吉布斯自由能最小）<br>等温等容：ΔA ≤ 0（亥姆霍兹自由能最小）</div>
<p>对实验室和生命体最常见的<strong>等温等压</strong>条件，判断反应能否自发，就看<strong>ΔG是否小于0</strong>。ΔG&lt;0自发进行；ΔG=0达到平衡；ΔG&gt;0非自发（需外界做功）。</p>
<h3>相变：潜热与突变</h3>
<p>水结成冰、铁熔成铁水，这些<strong>相变</strong>发生时，两相（如固/液）共存，温度和压强相等。<strong>一级相变</strong>（固液气转变）伴随体积和熵的突跳（需要吸收/放出潜热）。</p>
<div class="formula-block"><span class="formula-label">克拉佩龙方程</span>dp/dT = L / (T·ΔV)<br>L=摩尔潜热，ΔV=摩尔体积变化<br>描述相平衡曲线（如水的沸点随压强）的斜率</div>
<p>当压强升高到"临界点"以上，气液差别消失（超临界流体），传统相变的突变特征不再明显——这是高压物理和化工分离技术的重要基础。</p>
<h3>微分关系与温度阈值</h3>
<div class="formula-block"><span class="formula-label">吉布斯关系</span>dG = -S dT + V dp + μ dN<br>恒温恒压反应：ΔG = ΔH - TΔS</div>
<p>若ΔH&gt;0且ΔS&gt;0，低温下焓代价占主导而非自发，高于T=ΔH/ΔS后熵项占主导并可能自发。克拉佩龙方程的斜率符号由L和ΔV共同决定：熔化潜热L&gt;0；多数物质液体体积更大，ΔV&gt;0，熔点随压强升高。水结冰时固态体积反而更大，按“液相减固相”的ΔV&lt;0，所以固液共存线斜率为负，加压会降低冰的熔点。</p>
<p><strong>统一方法：</strong>先根据外界控制量选择能够取极小值的势函数，再把温度、压强变化写成势的微分响应；比较两相时，则要求共存条件下化学势相等。自发方向、平衡点和相界线看似是不同问题，本质上都来自在给定约束下寻找热力学势允许的稳定状态。</p>`,
    quiz:[{ question:"综合全文，为什么判断自发过程或相平衡时必须先明确系统约束？", options:["A. 不同温度、压强和体积约束对应不同势函数与极值判据，相变方向还取决于熵和体积变化","B. 所有约束下都只需判断内能是否最大，势函数选择不会改变判据","C. 吉布斯自由能可以在任意约束下使用，而且与温度和压强无关","D. 相平衡只由潜热大小决定，体积变化不会进入共存条件"], answerIndex:0 },
           { question:"材料如何用同一热力学框架解释反应的温度依赖和水的反常熔点变化？", options:["A. 两者都只由压力大小决定，焓、熵和体积变化只是次要修正","B. 两者都说明平衡状态的熵必须为零，因此相变方向不会改变","C. 反应由焓熵竞争决定，水的共存线方向还由潜热与相变体积共同决定","D. 水的反常行为说明克拉佩龙方程在异常物质上完全失效"], answerIndex:2 }] }
);
