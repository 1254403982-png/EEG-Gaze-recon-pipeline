window.questionBank = window.questionBank || {};
window.questionBank.easy = window.questionBank.easy || [];
window.questionBank.easy.push(
  { id:11, title:"矩阵秩与向量组线性相关性", domain:"数学", difficulty:"低", diffClass:"is-low",
    summary:"矩阵的秩反映了其中包含多少真正的独立信息，向量组的线性相关与否由秩与向量个数的关系判定。",
    quickQs:["矩阵秩的几何直觉","如何判断向量组线性相关","给我出道练习题","用通俗语言解释"],
    content:`<p>假设你有5个向量，但其中3个可以由另外2个"组合"出来——那么这组向量里真正独立的信息其实只有2份。"<strong>秩</strong>"（rank）就是用来度量"真正的独立信息量"的概念。</p>
<h3>什么是秩？</h3>
<p>对于一个 m×n 矩阵 A，它的<strong>秩</strong> rank(A) 等于其行向量组（或列向量组）中<strong>线性无关向量的最大个数</strong>。直观理解：秩告诉你这个矩阵"实质上"是几维的信息。一个3×3矩阵的秩最多是3，如果秩只有2，说明它的三行（或三列）中有一行是"多余"的——可以被其他行线性表示出来。</p>
<div class="formula-block"><span class="formula-label">秩的重要性质</span>
rank(A) = rank(Aᵀ) （行秩 = 列秩）<br>
rank(AB) ≤ min(rank(A), rank(B)) （乘积的秩不超过因子的秩）</div>
<h3>线性相关 vs 线性无关</h3>
<p>给定向量组 v₁, v₂, ..., vₙ。如果能找到一组不全为零的数 c₁, c₂, ..., cₙ 使得 c₁v₁ + c₂v₂ + ... + cₙvₙ = 0（零向量），就说这些向量<strong>线性相关</strong>；否则称它们<strong>线性无关</strong>。</p>
<p>判定方法非常简洁：设向量个数为 n，则</p>
<div class="formula-block"><span class="formula-label">相关性判定定理</span>
秩 &lt; n ⇔ 线性相关（有多余/依赖的向量）<br>
秩 = n ⇔ 线性无关（每个向量都贡献独立信息）</div>
<p>几何理解：二维平面内3个向量必然线性相关（最多2个独立）；三维空间中4个向量也必然线性相关。超出的维度必然产生"依赖"。</p>
<h3>秩与线性方程组的解</h3>
<p>秩还有个直接用处：判断线性方程组 Ax=b 有没有解、有多少解。设未知数个数为 n，则：<strong>秩(A) = 秩([A|b]) = n</strong> 时有唯一解；<strong>秩(A) = 秩([A|b]) &lt; n</strong> 时有无穷多解；若增广矩阵秩大于系数矩阵秩，则方程组矛盾、无解。一句话：<strong>秩告诉你方程组里"真正独立的方程"有多少</strong>。</p>`,
    quiz:[{ question:"三维空间中的4个向量一定是？", options:["A. 线性无关","B. 线性相关","C. 可能相关也可能无关","D. 无法判断"], answerIndex:1 },
           { question:"若矩阵A是4×5且rank(A)=3，则其列向量中有多少个是线性无关的？", options:["A. 3个","B. 4个","C. 5个","D. 无法确定"], answerIndex:0 }] }
);
