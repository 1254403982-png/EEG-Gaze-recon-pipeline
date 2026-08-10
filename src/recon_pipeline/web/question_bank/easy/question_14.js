window.questionBank = window.questionBank || {};
window.questionBank.easy = window.questionBank.easy || [];
window.questionBank.easy.push(
  { id:14, title:"细胞呼吸与ATP合成", domain:"生物", difficulty:"低", diffClass:"is-low",
    summary:"细胞通过呼吸作用分解有机物获取能量，ATP是细胞通用的能量货币，有氧呼吸效率远高于无氧呼吸。",
    quickQs:["有氧呼吸和无氧呼吸的区别","ATP为什么被称为能量货币","给我出道练习题","用通俗语言解释"],
    content:`<p>你的每一次心跳、每一次思考、每一个动作都需要能量。细胞通过<strong>呼吸作用</strong>分解有机物（主要是葡萄糖）来获取能量，并把能量储存在一种叫ATP的小分子中。</p>
<h3>ATP：细胞的通用能量货币</h3>
<p>ATP（腺苷三磷酸）就像一块充好电的电池。它由腺苷和三个磷酸基团组成，末端的磷酸键含有大量化学能（称为"高能磷酸键"）。当细胞需要能量时，ATP水解断裂最后一个磷酸键变成ADP，释放能量供细胞使用。然后细胞通过呼吸作用重新把ADP"充电"为ATP。一个人每天合成和水解的ATP重量约等于自身体重！</p>
<h3>有氧呼吸：高效的三阶段过程</h3>
<p>在有氧气的情况下，细胞彻底分解葡萄糖：</p>
<div class="formula-block"><span class="formula-label">总反应式</span>C₆H₁₂O₆ + 6O₂ → 6CO₂ + 6H₂O + 约30-32 ATP</div>
<p>分三个阶段进行：①<strong>糖酵解</strong>（在细胞质中，葡萄糖→丙酮酸，净产2ATP）；②<strong>柠檬酸循环</strong>（在线粒体基质中，产少量ATP和大量[H]）；③<strong>氧化磷酸化</strong>（在线粒体内膜上，[H]驱动ATP合酶，产大量ATP——约占90%以上）。</p>
<h3>无氧呼吸：缺氧时的应急方案</h3>
<p>缺氧时细胞只能走完第一阶段（糖酵解），产物不同：<strong>酵母菌</strong>产生酒精+CO₂（酿酒原理），<strong>动物肌肉</strong>产生乳酸（剧烈运动后肌肉酸痛的原因）。无氧呼吸只产2ATP，效率远低于有氧呼吸，但胜在不需要氧气、速度更快。</p>
<h3>ATP合酶：分子旋转马达</h3>
<p>有氧呼吸90%以上的ATP都来自氧化磷酸化，核心是一台精妙的<strong>分子马达——ATP合酶</strong>。米切尔提出的"化学渗透假说"解释了原理：电子传递链把质子（H⁺）从线粒体基质泵到膜间隙，形成跨内膜的<strong>质子浓度梯度</strong>（像水坝蓄水）。质子顺浓度梯度通过ATP合酶的通道回流时，驱动酶头部像旋转涡轮一样转动，把ADP和磷酸"拧"成ATP。这个旋转的"旋钮"每秒可合成上百个ATP分子，是生命界最小的马达。2016年揭示其原子结构的科学家荣获诺贝尔奖——这也说明为何我们必须持续呼吸：氧气正是电子传递链的"最终电子受体"，没有它，质子梯度无法维持，ATP生产就会停摆。</p>`,
    quiz:[{ question:"人体剧烈运动后肌肉酸痛的主要原因是什么物质堆积？", options:["A. 酒精","B. 乳酸","C. CO₂","D. ATP"], answerIndex:1 },
           { question:"有氧呼吸三个阶段中，产生ATP最多的是哪个阶段？", options:["A. 糖酵解","B. 柠檬酸循环","C. 氧化磷酸化","D. 三者差不多"], answerIndex:2 }] }
);
