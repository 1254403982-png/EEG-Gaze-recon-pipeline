window.questionBank = window.questionBank || {};
window.questionBank.medium = window.questionBank.medium || [];
window.questionBank.medium.push(
  { id:27, title:"特征值、特征向量与矩阵对角化", domain:"数学", difficulty:"中", diffClass:"is-moderate",
    summary:"特征值表示矩阵对特征向量的缩放倍数，可对角化矩阵可通过相似变换简化幂运算，在降维和动力学中应用广泛。",
    quickQs:["特征值的几何意义","矩阵可对角化的条件","给我出道练习题","用通俗语言解释"],
    content:`<p>矩阵不只是数字的方阵，它可以被理解为一种"变换"——把一个向量变成另一个向量。大多数向量经过矩阵变换后，方向都变了；但有一类特殊的向量，变换后<strong>只被拉长或缩短，方向不变</strong>——它们就是<strong>特征向量</strong>，对应的拉伸倍数就是<strong>特征值</strong>。</p>
<h3>定义与几何意义</h3>
<p>对于方阵 A，若存在非零向量 x 和数 λ 使得 Ax = λx，则 λ 是特征值，x 是对应的特征向量。</p>
<div class="formula-block"><span class="formula-label">特征方程</span>|A - λI| = 0<br>展开得到关于λ的n次多项式，其根即特征值</div>
<p><strong>几何直觉</strong>：矩阵A作用在特征向量x上，只是把x放大了λ倍，不旋转、不歪斜。特征值λ就是这个"缩放因子"。</p>
<h3>特征值的性质</h3>
<div class="formula-block"><span class="formula-label">两条核心性质</span>
1. 迹：tr(A) = Σλᵢ = 对角线元素之和<br>
2. 行列式：|A| = Πλᵢ（所有特征值之积）</div>
<p>由第2条可直接推出：A 可逆 ⇔ 所有特征值都不为0。</p>
<h3>矩阵对角化与应用</h3>
<p>如果 A 有 n 个线性无关的特征向量，就能拼成一个可逆矩阵 P，使得 P⁻¹AP = Λ（Λ是对角矩阵，对角元为特征值）。这个操作叫<strong>对角化</strong>。</p>
<div class="formula-block"><span class="formula-label">对角化的威力</span>Aᵏ = PΛᵏP⁻¹<br>计算A的高次幂时，只需算Λᵏ（对角阵幂 = 各对角元求k次幂），大幅简化！</div>
<p>应用极其广泛：主成分分析(PCA)数据降维、Google PageRank网页排序、物理系统的振动模态分析、马尔可夫链长期行为预测等。</p>`,
    quiz:[{ question:"矩阵特征值的几何意义是？", options:["A. 向量旋转的角度","B. 特征向量被缩放的倍数","C. 矩阵的维度","D. 向量的数量"], answerIndex:1 },
           { question:"设矩阵A的特征值为 λ₁=2, λ₂=3，则A的行列式|A|等于？", options:["A. 5","B. 6","C. 2","D. 3"], answerIndex:1 }] }
);
