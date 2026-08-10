window.questionBank = window.questionBank || {};
window.questionBank.medium = window.questionBank.medium || [];
window.questionBank.medium.push(
  { id:28, title:"电磁感应定律与楞次定律", domain:"物理", difficulty:"中", diffClass:"is-moderate",
    summary:"法拉第电磁感应定律定量描述磁通量变化产生的感应电动势，楞次定律定性判定感应电流的方向，两者共同构成电磁感应的理论基础。",
    quickQs:["法拉第定律的数学形式","楞次定律的应用","给我出道练习题","用通俗语言解释"],
    content:`<p>发电机、变压器、无线充电——这些改变世界的发明背后是同一个原理：<strong>电磁感应</strong>。1831年法拉第发现，磁场的变化可以产生电流。这彻底打通了"磁"与"电"，让人类进入了电气时代。</p>
<h3>法拉第电磁感应定律</h3>
<p>当穿过一个闭合回路的<strong>磁通量</strong> Φ（可以理解为穿过线圈的"磁力线总数"）发生变化时，回路中就会产生感应电动势 ε。</p>
<div class="formula-block"><span class="formula-label">法拉第定律</span>ε = -dΦ/dt<br>ε = 感应电动势，Φ = 磁通量 = ∫B·dS<br>负号表示电动势方向与磁通量变化方向相反</div>
<h3>磁通量变化的三种方式</h3>
<ul style="padding-left:20px;">
<li><strong>磁场变化</strong>：磁铁靠近/远离线圈（B随时间变）</li>
<li><strong>回路运动</strong>：线圈在磁场中切割磁感线（B不变，位置变）</li>
<li><strong>回路变形</strong>：线圈面积或朝向改变（B不变，形状变）</li>
</ul>
<h3>楞次定律：判断方向</h3>
<p>法拉第定律告诉你"有多大"感应电动势，<strong>楞次定律</strong>告诉你"电流往哪流"：</p>
<div class="formula-block"><span class="formula-label">楞次定律</span>感应电流产生的磁场，总是<strong>阻碍</strong>引起它的磁通量变化。</div>
<p>换句话说：磁通量要增加，感应磁场就反向去抵消；磁通量要减少，感应磁场就同向去补充。这本质上是<strong>能量守恒</strong>的体现——如果感应电流"助长"了变化，就会无限放大能量，违反守恒。所以感应总是"反抗"原因。</p>`,
    quiz:[{ question:"楞次定律的核心作用是？", options:["A. 增强磁通量","B. 阻碍磁通量变化","C. 消除磁场","D. 生成磁场"], answerIndex:1 },
           { question:"当穿过闭合线圈的磁通量增加时，感应电流产生的磁场方向与原磁场方向？", options:["A. 相同","B. 相反","C. 垂直","D. 平行"], answerIndex:1 }] }
);
