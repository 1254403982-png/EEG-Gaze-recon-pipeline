window.questionBank = window.questionBank || {};
window.questionBank.easy = window.questionBank.easy || [];
window.questionBank.easy.push(
  { id:9, title:"肾素-血管紧张素系统与血压调节", domain:"医学", difficulty:"低", diffClass:"is-low",
    summary:"RAAS是人体调节血压的核心激素系统，通过肾素-血管紧张素-醛固酮的级联反应升高血压，其抑制剂是临床一线降压药。",
    quickQs:["RAAS级联的各个步骤","ACE抑制剂为什么能降压","给我出道练习题","用通俗语言解释"],
    content:`<p>人体血压是如何维持稳定的？当你大量失血或脱水时，血压会下降，身体有一套精密的激素系统来"紧急升压"——这就是<strong>肾素-血管紧张素-醛固酮系统（RAAS）</strong>。</p>
<h3>RAAS级联反应链</h3>
<p>整个过程像一个多米诺骨牌链条：</p>
<div class="formula-block"><span class="formula-label">级联过程</span>
① 血压 ↓ → 肾脏感知 → 分泌<strong>肾素</strong><br>
② 肾素切割血管紧张素原 → 生成 <strong>Ang I</strong>（10肽，本身不活跃）<br>
③ <strong>ACE酶</strong>（血管紧张素转换酶）作用于Ang I → 生成 <strong>Ang II</strong>（8肽，活性最强！）<br>
④ Ang II 发挥四大效应 → 血压 ↑</div>
<h3>Ang II 的四大升压效应</h3>
<ul style="padding-left:20px;">
<li><strong>直接收缩血管</strong> → 外周阻力瞬间升高</li>
<li><strong>刺激醛固酮释放</strong> → 肾脏重吸收Na⁺和水 → 血容量增加</li>
<li><strong>促进口渴感</strong> → 主动喝水补充体液</li>
<li><strong>增强交感神经</strong> → 心跳加快、心输出量增加</li>
</ul>
<h3>ACE抑制剂：高血压一线药物</h3>
<p>既然ACE是将Ang I转化为强效Ang II的关键"转换器"，那阻断它就能阻断整个升压链条。<strong>ACE抑制剂</strong>（药名后缀"-pril"，如依那普利）就是这样工作的。副作用包括干咳（因为ACE同时还降解一种叫缓激肽的物质，抑制后缓激肽蓄积刺激呼吸道）和高钾血症。</p>
<h3>醛固酮：保钠保水的"慢通道"</h3>
<p>Ang II 还会刺激肾上腺皮质释放<strong>醛固酮</strong>，促进肾脏远曲小管重吸收 Na⁺ 和水、排出 K⁺。与 Ang II 的"秒级"缩血管不同，醛固酮通过增加血容量来升压，起效慢却更持久——两者一快一慢，构成 RAAS 的双引擎。</p>
<h3>完整的负反馈闭环</h3>
<p>整个系统是一个精密的<strong>负反馈稳压器</strong>：血压↓ → 肾脏分泌肾素 → Ang II 与醛固酮↑ → 血管收缩 + 血容量↑ → 血压回升 → 反向抑制肾素分泌。正因如此，RAAS 抑制剂（ACEi / ARB）成为高血压、心衰的一线用药。</p>
<h3>警惕：肾血管性高血压</h3>
<p>当肾动脉狭窄导致肾脏长期缺血时，RAAS 会被"误以为"全身低血压而持续过度激活，引起<strong>顽固性高血压</strong>。这类患者若用 ACEi 反而危险——因为出球小动脉被扩张会进一步降低肾小球滤过压，可能诱发急性肾损伤。</p>`,
    quiz:[{ question:"RAAS级联中哪种物质的升压能力最强？", options:["A. 肾素","B. Ang I（10肽）","C. Ang II（8肽）","D. 醛固酮"], answerIndex:2 },
           { question:"ACE抑制剂（如依那普利）引起干咳的原因是什么？", options:["A. 直接刺激气道","B. 缓激肽蓄积","C. Ang II增多","D. 醛固酮减少"], answerIndex:1 }] }
);
