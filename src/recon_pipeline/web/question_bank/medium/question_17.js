window.questionBank = window.questionBank || {};
window.questionBank.medium = window.questionBank.medium || [];
window.questionBank.medium.push(
  { id:17, title:"微积分基本定理及其推广", domain:"数学", difficulty:"中", diffClass:"is-moderate",
    summary:"微积分基本定理连接了微分和积分，格林公式和高斯公式将其推广到二维和三维，揭示边界与内部的深刻联系。",
    quickQs:["微积分基本定理的直观含义","格林公式和高斯公式的联系","给我出道练习题","用通俗语言解释"],
    content:`<p>微积分基本定理（牛顿-莱布尼茨公式）可能是整个数学中最有用的一个公式。它说的是：<strong>积分和微分互为逆运算</strong>。具体来说，如果你先把函数f微分得到f'，再把f'积分回去，就得到了f在端点的差值。这个看起来简单的结论有一个深刻的推广——它不只是在一维成立，在高维中也存在类似的"边界-内部"关系。</p>
<h3>一维：微积分基本定理</h3>
<div class="formula-block"><span class="formula-label">牛顿-莱布尼茨公式</span>∫ₐᵇ f'(x) dx = f(b) - f(a)</div>
<p>左边是f'在区间[a,b]上的"累积总量"（积分），右边是f在区间两端（边界！）的值之差。注意到关键词了吗？——<strong>内部积分 = 边界值之差</strong>。这个模式会在更高维度中反复出现。</p>
<h3>二维：格林公式</h3>
<p>在平面上，沿一条闭合曲线C的线积分等于曲线所围区域D上的二重积分：</p>
<div class="formula-block"><span class="formula-label">格林公式</span>∮_C (P dx + Q dy) = ∬_D (∂Q/∂x - ∂P/∂y) dA</div>
<p>左边是沿边界C的"环绕累积"，右边是区域D内部的"面积分"。又一次：<strong>边界上的积分 = 内部的积分</strong>。格林公式在物理学中用来计算功和流量。</p>
<h3>三维：高斯散度定理</h3>
<p>推广到三维空间：封闭曲面S上的通量积分等于曲面所围体积V内的散度积分：</p>
<div class="formula-block"><span class="formula-label">高斯散度定理</span>∯_S F · dS = ∭_V (∇ · F) dV</div>
<p>这就是电磁学中麦克斯韦方程组里"高斯定律"的数学基础。从一维到三维，形式都是<strong>边界积分 = 内部积分</strong>，只是维度不同而已。这个统一的思想后来被广义斯托克斯定理推向了最高潮。</p>`,
    quiz:[{ question:"微积分基本定理∫f'dx=f(b)-f(a)的核心含义是什么？", options:["A. 微分和积分互为逆运算","B. 积分总是大于微分","C. f(b)总是大于f(a)","D. 仅适用于多项式函数"], answerIndex:0 },
           { question:"格林公式和高斯公式的共同数学结构是？", options:["A. 点积等于叉积","B. 边界上的积分等于区域内部的积分","C. 曲线积分等于曲面积分","D. 散度等于旋度"], answerIndex:1 }] }
);
