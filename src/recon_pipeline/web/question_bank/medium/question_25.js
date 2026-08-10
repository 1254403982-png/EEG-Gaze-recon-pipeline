window.questionBank = window.questionBank || {};
window.questionBank.medium = window.questionBank.medium || [];
window.questionBank.medium.push(
  { id:25, title:"心脏电生理与心律失常", domain:"医学", difficulty:"中", diffClass:"is-moderate",
    summary:"心肌动作电位分为5个时期，Ca²⁺/K⁺/Na⁺离子流塑造各期特征，折返激动是心动过速的主要电生理机制。",
    quickQs:["心肌动作电位的五个时期","折返激动需要什么条件","给我出道练习题","用通俗语言解释"],
    content:`<p>心脏为什么会规律跳动？靠的是一套精密的"电系统"。心肌细胞受到刺激时，细胞膜内外的带电离子（Na⁺、K⁺、Ca²⁺）快速进出，产生一股电流——这就是<strong>心肌动作电位</strong>。整颗心脏就像一串被依次点亮又熄灭的灯。</p>
<h3>心肌动作电位的五个时期</h3>
<table class="data-table">
<tr><th>期</th><th>名称</th><th>主导离子流</th><th>膜电位变化</th></tr>
<tr><td>0期</td><td>快速去极化</td><td>Na⁺ 快速内流</td><td>-90mV → +30mV（约1ms）</td></tr>
<tr><td>1期</td><td>快速复极初期</td><td>K⁺ 瞬时外流</td><td>+30mV → 0mV</td></tr>
<tr><td>2期</td><td>平台期</td><td>Ca²⁺内流 ≈ K⁺外流</td><td>0mV 维持100-150ms（心肌特有）</td></tr>
<tr><td>3期</td><td>快速复极末期</td><td>K⁺ 外流占主导</td><td>0mV → -90mV</td></tr>
<tr><td>4期</td><td>静息/自动去极化</td><td>离子泵恢复梯度</td><td>稳定在 -90mV</td></tr>
</table>
<p>第2期<strong>平台期</strong>是心肌特有的——Ca²⁺内流与K⁺外流刚好平衡，使心肌收缩期延长，保证心脏充分泵血，也防止心肌像骨骼肌那样强直（持续）收缩。</p>
<h3>折返激动：心动过速的电机制</h3>
<p>大多数心动过速源于一种叫<strong>折返</strong>的异常电路。想象一条环形跑道，运动员（电信号）绕着跑，如果前方的人还没离开（组织仍在不应期），后面的就只能停下；但如果某条路径传导特别慢，等信号绕回来时前方已经"重置"可以再激动一次——信号就会绕圈不停跑，心跳就失控了。</p>
<div class="formula-block"><span class="formula-label">折返三要素</span>
1. 解剖或功能性环路（两条传导路径）<br>
2. 单向阻滞（一条路径只能顺向传导）<br>
3. 传导速度足够慢，使环路前端已脱离不应期</div>
<p>典型例子是WPW综合征：心脏多了一条旁路，与正常房室传导形成折返环。射频消融术通过烧断这条旁路来治疗，成功率超过95%。</p>
<h3>心脏的"天然起搏点"</h3>
<p>心脏之所以能自主跳动，靠的是<strong>自律细胞</strong>。正常心跳指令发源于右心房的<strong>窦房结</strong>——它无需外界刺激就能自动、节律地去极化（对应动作电位4期的"自动去极化"），像天然节拍器，每分钟发出约60~100次冲动。冲动经房室结延迟后传遍心室，保证心房先收缩、心室后收缩的协调顺序。若窦房结功能异常（病态窦房结综合征），医生可植入<strong>人工心脏起搏器</strong>替代它发出节律信号。</p>`,
    quiz:[{ question:"心肌动作电位第2期（平台期）的形成机制是？", options:["A. Na⁺快速内流","B. K⁺快速外流","C. Ca²⁺内流与K⁺外流达到平衡","D. Na⁺-K⁺泵工作"], answerIndex:2 },
           { question:"折返激动引发心动过速，必须满足的条件不包括以下哪项？", options:["A. 存在解剖或功能性环路","B. 单向传导阻滞","C. 传导速度足够慢","D. 心脏完全停搏"], answerIndex:3 }] }
);
