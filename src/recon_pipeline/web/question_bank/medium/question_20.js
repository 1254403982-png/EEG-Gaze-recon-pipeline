window.questionBank = window.questionBank || {};
window.questionBank.medium = window.questionBank.medium || [];
window.questionBank.medium.push(
  { id:20, title:"CRISPR-Cas9基因编辑技术", domain:"生物", difficulty:"中", diffClass:"is-moderate",
    summary:"CRISPR-Cas9是一把分子剪刀，能在DNA的特定位置进行精确剪切，开启了基因治疗和生物育种新时代。",
    quickQs:["Cas9如何找到目标位置","基因敲除和基因敲入的区别","给我出道练习题","用通俗语言解释"],
    content:`<p>想象一把能在几十亿个碱基对的基因组中找到特定位置并进行精确剪切的"分子手术刀"——这就是CRISPR-Cas9。这项2012年开发的技术彻底变革了生物学研究，2020年荣获诺贝尔化学奖。</p>
<h3>系统组成：GPS导航 + 剪刀</h3>
<p>CRISPR-Cas9系统由两部分组成：<br>① <strong>sgRNA（向导RNA）</strong>：一段20个碱基的序列，像GPS导航一样与目标DNA精确互补配对，指引Cas9到达目标位置。<br>② <strong>Cas9蛋白</strong>：一把"分子剪刀"，一旦到达指定位置就切断DNA双链。<br>还有一个关键细节：Cas9在剪切前必须识别目标DNA旁边的一个短序列标记叫<strong>PAM</strong>（通常是NGG），这保证了Cas9不会乱切——就像门锁一样，有钥匙（sgRNA）还不够，还得有正确的锁（PAM）匹配才能开门。</p>
<h3>剪切之后的两条修复路径</h3>
<p>DNA被切断后，细胞会启动修复机制，科学家正好"借用"这个修复过程来实现编辑目的：</p>
<table class="data-table">
<tr><th>修复路径</th><th>特点</th><th>实现的目标</th></tr>
<tr><td>NHEJ<br>(非同源末端连接)</td><td>直接把断端粘起来，容易出错</td><td><strong>基因敲除</strong>：引入突变使基因失活</td></tr>
<tr><td>HDR<br>(同源定向修复)</td><td>以提供的外源DNA为模板精确修复</td><td><strong>基因敲入</strong>：精确插入想要的基因序列</td></tr>
</table>
<h3>应用前景与挑战</h3>
<p>CRISPR已被用于治疗镰刀型细胞贫血症等遗传疾病（临床试验阶段）、改良农作物（高产抗虫）、以及创建疾病模型动物。主要挑战包括脱靶效应（切错了位置）和递送效率（如何把CRISPR送入体内的目标细胞）。伦理争议也很大——2018年"基因编辑婴儿"事件引发了全球关于人类生殖系基因编辑边界的激烈讨论。</p>
<h3>升级版：碱基编辑与先导编辑</h3>
<p>最初的CRISPR-Cas9是"剪刀式"的，必须切断DNA双链，容易因NHEJ出错或引发细胞凋亡。2020年前后发展起来的<strong>碱基编辑</strong>（base editing）不再切断双链，而是直接用脱氨酶把单个碱基"改写"——例如把致病的A·T碱基对直接变成G·C，实现精准点突变而不留断裂伤口。<strong>先导编辑</strong>（prime editing）更进一步：用改造后的Cas9（只切一条链）配合一段带"修改蓝图"的pegRNA，像文字处理器一样"搜索-替换"任意短序列。它们把基因编辑从"粗糙剪切"推进到"精确改写"时代，为更多遗传病治疗带来希望。</p>`,
    quiz:[{ question:"CRISPR系统中引导Cas9到达目标位置的导航工具是什么？", options:["A. Cas9蛋白自身","B. sgRNA（向导RNA）","C. PAM序列","D. DNA聚合酶"], answerIndex:1 },
           { question:"想要精确修改基因（替换/插入特定序列），应利用哪条修复路径？", options:["A. NHEJ","B. HDR","C. 两条都可以","D. 两者都不行"], answerIndex:1 }] }
);
