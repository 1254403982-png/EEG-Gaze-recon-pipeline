window.questionBank = window.questionBank || {};
window.questionBank.medium = window.questionBank.medium || [];
window.questionBank.medium.push(
  { id:30, title:"特异性免疫与免疫记忆", domain:"生物", difficulty:"中", diffClass:"is-moderate",
    summary:"特异性免疫分为体液免疫（B细胞/抗体）和细胞免疫（T细胞），具有高度特异性和记忆性，是疫苗接种的理论基础。",
    quickQs:["体液免疫与细胞免疫的区别","免疫记忆是如何形成的","给我出道练习题","用通俗语言解释"],
    content:`<p>为什么得过水痘的人一般不会再得？为什么疫苗能预防疾病？秘密在于人体的<strong>特异性免疫系统</strong>——它不仅能精准识别"敌人"，还能"记住"敌人，下次遇到时反应更快更猛。</p>
<h3>体液免疫（B细胞介导）：对付细胞外的敌人</h3>
<p>B细胞表面有专门的受体(BCR)，能识别游离在体液中的抗原（如细菌、病毒颗粒）。被激活后，B细胞分化为<strong>浆细胞</strong>，大量分泌<strong>抗体</strong>。抗体像"智能导弹"一样精准结合病原体：</p>
<div class="formula-block"><span class="formula-label">抗体的三大作用</span>
1. <strong>中和</strong>：结合病毒/毒素，阻止其进入细胞<br>
2. <strong>调理</strong>：标记病原体，方便吞噬细胞"吃掉"<br>
3. <strong>激活补体</strong>：引发级联反应直接破坏病原体膜</div>
<h3>细胞免疫（T细胞介导）：对付细胞内的敌人</h3>
<p>当病毒已经躲进细胞内部，抗体进不去。这时需要<strong>T细胞</strong>出马：</p>
<table class="data-table">
<tr><th>T细胞类型</th><th>功能</th><th>标记</th></tr>
<tr><td>辅助性T细胞(CD4⁺)</td><td>分泌细胞因子，指挥B细胞和杀伤T细胞</td><td>CD4</td></tr>
<tr><td>细胞毒性T细胞(CD8⁺)</td><td>直接识别并杀死被感染细胞</td><td>CD8</td></tr>
</table>
<h3>免疫记忆：疫苗的原理</h3>
<p>初次感染时，免疫系统花了好几天才组织起有效反击。但在此过程中，一部分B细胞和T细胞转化成了<strong>记忆细胞</strong>——长期存活、保持"敌情记忆"。当<strong>再次</strong>遇到相同病原体时，记忆细胞迅速活化，几小时内就发动比第一次强得多、快得多的<strong>二次应答</strong>。疫苗正是利用这个原理：先用减毒/灭活的病原体"演练"一次，让身体提前准备好记忆细胞，真病毒来袭时就能秒杀。</p>
<p>补充两点：<strong>① 主动免疫 vs 被动免疫</strong>——打疫苗（让身体自己产生记忆细胞）属于主动免疫，效果持久；直接注射抗体（如破伤风抗毒素）属于被动免疫，见效快但几个月内就被代谢掉。<strong>② 二次应答的特征</strong>——再次感染时抗体浓度上升更快、峰值更高、维持更久，这正是"得过一次就不容易再得"的底层原因。</p>`,
    quiz:[{ question:"清除已经进入细胞内部的病毒，主要依赖哪种特异性免疫？", options:["A. 体液免疫（抗体）","B. 细胞免疫（细胞毒性T细胞）","C. 皮肤物理屏障","D. 吞噬细胞非特异性吞食"], answerIndex:1 },
           { question:"接种疫苗后人体能产生长期保护，主要依赖什么机制？", options:["A. 抗体永久存在于血液中","B. 形成了免疫记忆细胞","C. 疫苗直接杀死了所有病原体","D. 皮肤屏障增强"], answerIndex:1 }] }
);
