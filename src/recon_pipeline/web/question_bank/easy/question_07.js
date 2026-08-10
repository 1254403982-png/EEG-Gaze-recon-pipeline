window.questionBank = window.questionBank || {};
window.questionBank.easy = window.questionBank.easy || [];
window.questionBank.easy.push(
  { id:7, title:"条件反射与学习机制", domain:"心理学", difficulty:"低", diffClass:"is-low",
    summary:"巴甫洛夫的经典条件反射建立刺激之间的联结，斯金纳的操作性条件反射通过行为后果塑造行为频率。",
    quickQs:["经典条件反射和操作性条件反射的区别","强化与惩罚的类型","给我出道练习题","用通俗语言解释"],
    content:`<p>心理学中关于"学习"有两个最重要的理论框架：<strong>经典条件反射</strong>研究的是被动关联学习（铃声→分泌唾液），<strong>操作性条件反射</strong>研究的是主动行为学习（按杠杆→得到食物）。两者机制完全不同。</p>
<h3>经典条件反射（巴甫洛夫）</h3>
<p>巴甫洛夫发现：每次给狗喂食前先摇铃，重复多次后，狗听到铃声就会流口水——铃声原本是"中性刺激"，通过与食物（无条件刺激）反复配对，变成了能引发唾液分泌的"条件刺激"。这就是<strong>经典条件反射</strong>：中性刺激 ↔ 有意义刺激之间建立了新的神经联结。</p>
<div class="formula-block"><span class="formula-label">关键现象</span><strong>消退</strong>：只响铃不给食物→反应逐渐消失<br><strong>泛化</strong>：类似铃声也引起反应<br><strong>分化</strong>：学会区分不同刺激</div>
<h3>操作性条件反射（斯金纳）</h3>
<p>斯金纳箱中的老鼠偶然按下了杠杆，得到了食物奖励。之后它会越来越频繁地按杠杆——因为<strong>行为带来了好的后果</strong>。斯金纳将行为后果分为四类：</p>
<ul style="padding-left:20px;">
<li><strong>正强化</strong>（给奖励）：行为↑ —— 例：做题对了得小红花</li>
<li><strong>负强化</strong>（去掉讨厌的东西）：行为↑ —— 例：系好安全带后提示音停止</li>
<li><strong>正惩罚</strong>（给厌恶刺激）：行为↓ —— 例：迟到被扣钱</li>
<li><strong>负惩罚</strong>（拿走好东西）：行为↓ —— 例：玩手机被没收</li>
</ul>
<p>特别值得注意的是：<strong>间歇性强化（有时给有时不给）比连续强化形成的习惯更难消退</strong>。这正是赌博让人上瘾的心理机制——老虎机就是一台完美的间歇强化机器。</p>`,
    quiz:[{ question:"通过行为后果来改变行为发生频率的学习方式叫做什么？", options:["A. 经典条件反射","B. 操作性条件反射","C. 观察学习","D. 潜伏学习"], answerIndex:1 },
           { question:"为什么赌博（如老虎机）特别容易让人上瘾？", options:["A. 因为赌徒意志力薄弱","B. 变比间歇强化使习惯极难消退","C. 赌场环境设计诱导","D. 金钱的边际效用递减"], answerIndex:1 }] }
);
