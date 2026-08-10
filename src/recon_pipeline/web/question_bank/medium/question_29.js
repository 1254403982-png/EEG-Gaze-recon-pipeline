window.questionBank = window.questionBank || {};
window.questionBank.medium = window.questionBank.medium || [];
window.questionBank.medium.push(
  { id:29, title:"配位化合物与配位平衡", domain:"化学", difficulty:"中", diffClass:"is-moderate",
    summary:"配位化合物由中心离子与配体通过配位键结合形成，稳定常数衡量配合物的稳定性，在生物和化学分析中有广泛应用。",
    quickQs:["配位键的特征","稳定常数的意义","给我出道练习题","用通俗语言解释"],
    content:`<p>你听说过"蓝瓶子"实验吗？向硫酸铜溶液中加入氨水，先产生蓝色沉淀，继续加氨水沉淀又溶解变成深蓝色溶液——这是因为生成了一种特殊的化合物：<strong>配位化合物（配合物）</strong>。它广泛存在于自然界和生命体中。</p>
<h3>配位化合物的组成</h3>
<p>配合物由<strong>中心离子</strong>（通常是金属离子，如Cu²⁺、Fe²⁺）和围绕它的<strong>配体</strong>（提供孤对电子的分子或离子，如NH₃、H₂O、Cl⁻）通过<strong>配位键</strong>结合而成。</p>
<div class="formula-block"><span class="formula-label">配合物结构</span>[中心离子 + n个配体]^(电荷) + 外界离子<br>例：[Cu(NH₃)₄]SO₄ 中：Cu²⁺是中心离子，NH₃是配体，配位数=4</div>
<h3>特殊的配位键：单方提供电子对</h3>
<p>普通共价键的共用电子对由双方各提供一个；而<strong>配位键</strong>的电子对完全由一方（配体，作为路易斯碱）提供，另一方（中心离子，提供空轨道）接受。这正是NH₃能让Cu²⁺沉淀"复活"的原因——NH₃的N原子有孤对电子，钻进Cu²⁺的空轨道形成配位键。</p>
<h3>配位平衡与稳定常数</h3>
<p>配位反应是可逆的，存在配位-解离平衡：</p>
<div class="formula-block"><span class="formula-label">配位平衡</span>Mⁿ⁺ + nL ⇌ [MLₙ]ⁿ⁺<br>稳定常数 K_f = [[MLₙ]ⁿ⁺] / ([Mⁿ⁺][L]ⁿ)<br>K_f 越大，配合物越稳定</div>
<h3>身边的配合物</h3>
<ul style="padding-left:20px;">
<li><strong>血液</strong>：血红蛋白中Fe²⁺与O₂配位，实现氧气运输</li>
<li><strong>医药</strong>：顺铂[Pt(NH₃)₂Cl₂]作为抗癌药物，与DNA配位阻止复制</li>
<li><strong>分析化学</strong>：EDTA与金属离子形成稳定配合物，用于滴定测浓度</li>
</ul>`,
    quiz:[{ question:"配位键的电子对来源是？", options:["A. 双方各提供一个","B. 配体单方提供","C. 中心离子单方提供","D. 无固定来源"], answerIndex:1 },
           { question:"配合物的稳定常数K_f越大，表示？", options:["A. 配合物越不稳定","B. 配合物越稳定","C. 配位数越多","D. 中心离子电荷越高"], answerIndex:1 }] }
);
