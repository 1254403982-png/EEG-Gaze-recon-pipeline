window.questionBank = window.questionBank || {};
window.questionBank.easy = window.questionBank.easy || [];
window.questionBank.easy.push(
  { id:4, title:"中心法则与基因表达", domain:"生物", difficulty:"低", diffClass:"is-low",
    summary:"中心法则描述遗传信息从DNA流向RNA再流向蛋白质的过程，转录和翻译是实现这一信息流的两个关键步骤。",
    quickQs:["转录和翻译的区别是什么","基因表达受哪些调控","给我出道练习题","用通俗语言解释"],
    content:`<p>你体内的每一个细胞都携带同一套DNA"说明书"，但皮肤细胞和神经细胞却长得完全不同。这是因为不同细胞"阅读"说明书的不同章节——这个过程叫做<strong>基因表达</strong>。1958年克里克提出<strong>中心法则</strong>，概括了遗传信息流动的方向：DNA → RNA → 蛋白质。</p>
<h3>第一步：转录（DNA → RNA）</h3>
<p>DNA存储着遗传密码，但它本身不能直接干活。细胞需要先把它"抄写"成一份副本——信使RNA（mRNA）。这个过程叫<strong>转录</strong>：RNA聚合酶沿着DNA模板链移动，按照碱基互补配对规则（A→U, T→A, G→C, C→G）合成mRNA链。就像把一本英文书翻译成中文摘要一样，mRNA携带了蛋白质合成所需的指令。</p>
<h3>第二步：翻译（RNA → 蛋白质）</h3>
<p>mRNA离开细胞核进入细胞质，在<strong>核糖体</strong>上被"翻译"成蛋白质。核糖体从mRNA的一端开始，每读取三个碱基（一个"密码子"）就对应一种氨基酸，tRNA负责搬运对应的氨基酸过来，氨基酸依次连接形成多肽链，折叠后成为有功能的蛋白质。</p>
<div class="formula-block"><span class="formula-label">遗传密码</span>4种碱基 → 4³=64个密码子 → 编码20种氨基酸+终止信号<br>多个密码子可以编码同一种氨基酸（简并性）</div>
<h3>调控：不是所有基因都在工作</h3>
<p>细胞通过多层面调控决定哪些基因表达、表达多少：表观遗传修饰（DNA甲基化）控制基因是否"可读"；转录因子决定哪些基因被抄写；可变剪接让同一个mRNA产生不同版本的蛋白质。正是这些调控机制让同样的DNA产生了200多种不同类型的细胞。</p>
<h3>中心法则的例外与扩展</h3>
<p>克里克最初表述为"DNA → RNA → 蛋白质"单向流动，但后来发现了重要例外：<strong>逆转录</strong>——某些病毒（如HIV）携带逆转录酶，能把RNA逆转录回DNA插入宿主基因组，把箭头变成"RNA → DNA"；<strong>端粒酶</strong>则用自身携带的RNA作模板修复DNA末端。现代生物学把中心法则修正为：遗传信息可从核酸流向核酸、从核酸流向蛋白质，但<strong>不能从蛋白质反向流向核酸</strong>。</p>
<h3>为什么是64个密码子？</h3>
<p>DNA用4种碱基（A、T、C、G）编码信息，每3个碱基组成一个密码子，组合数为：</p>
<div class="formula-block"><span class="formula-label">密码子总数</span>$$4^3 = 64$$<br>其中61个编码20种氨基酸，3个是终止信号</div>
<p>64个密码子对应20种氨基酸，意味着<strong>简并性</strong>——同一种氨基酸常由多个密码子编码（如亮氨酸有6个）。这种冗余并非浪费：它让DNA复制或转录中的某些突变"同义"（密码子变了但氨基酸不变），从而缓冲有害突变，提高生命的稳健性。</p>`,
    quiz:[{ question:"中心法则中遗传信息的正常流动方向是？", options:["A. 蛋白质→RNA→DNA","B. DNA→RNA→蛋白质","C. RNA→DNA→蛋白质","D. 蛋白质→DNA→RNA"], answerIndex:1 },
           { question:"核糖体的功能相当于什么？", options:["A. DNA复印机","B. mRNA→蛋白质的翻译机器","C. 能量工厂","D. 细胞的消化器官"], answerIndex:1 }] }
);
