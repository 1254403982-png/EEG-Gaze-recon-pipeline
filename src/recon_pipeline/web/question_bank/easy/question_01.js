window.questionBank = window.questionBank || {};
window.questionBank.easy = window.questionBank.easy || [];
window.questionBank.easy.push(
  { id:1, title:"线性空间与线性变换", domain:"数学", difficulty:"低", diffClass:"is-low",
    summary:"线性空间由八条公理定义了向量加法和数乘的代数结构，线性变换保持线性组合关系，其矩阵表示依赖于基的选择。",
    quickQs:["线性空间的8条公理","基变换与矩阵表示","给我出道练习题","用通俗语言解释"],
    content:`<p>线性空间（也叫向量空间）是线性代数的研究对象。简单来说，它是一个集合，里面的元素（称为"向量"）可以做加法和数乘运算，并且满足八条基本规则。</p>
<h3>八条公理</h3>
<p>对于任意 u, v, w ∈ V 和 α, β ∈ F（数域），必须满足：</p>
<table class="data-table">
<tr><th>编号</th><th>公理名称</th><th>含义</th></tr>
<tr><td>A1</td><td>加法交换律</td><td>u + v = v + u</td></tr>
<tr><td>A2</td><td>加法结合律</td><td>(u + v) + w = u + (v + w)</td></tr>
<tr><td>A3</td><td>加法单位元</td><td>存在零向量 0，使 u + 0 = u</td></tr>
<tr><td>A4</td><td>加法逆元</td><td>每个 u 都有 -u，使 u + (-u) = 0</td></tr>
<tr><td>M1</td><td>数乘单位元</td><td>1·u = u</td></tr>
<tr><td>M2</td><td>数乘结合律</td><td>α(βu) = (αβ)u</td></tr>
<tr><td>M3</td><td>对加法的分配律</td><td>α(u + v) = αu + αv</td></tr>
<tr><td>M4</td><td>对数乘的分配律</td><td>(α + β)u = αu + βu</td></tr>
</table>
<h3>线性变换</h3>
<p>映射 T: V → W 称为<strong>线性变换</strong>，如果它满足 T(αu + βv) = αT(u) + βT(v)。直观理解：线性变换"保持向量的线性组合关系不变"。一个线性变换完全由它在一组基上的作用决定——知道了基向量被映射到哪儿，所有向量的像就都确定了。这就是为什么线性变换可以用矩阵来表示。</p>`,
    quiz:[{ question:"线性变换必须满足的核心条件是？", options:["A. 保持向量长度不变","B. 保持线性组合关系","C. 保持向量方向不变","D. 保持矩阵对称"], answerIndex:1 },
           { question:"为什么说线性变换可以用矩阵表示？", options:["A. 矩阵一定是对称的","B. 它由在基上的作用完全决定","C. 所有变换都是线性的","D. 矩阵的行列式为零"], answerIndex:1 }] }
);
