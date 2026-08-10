window.questionBank = window.questionBank || {};
window.questionBank.medium = window.questionBank.medium || [];
window.questionBank.medium.push(
  { id:32, title:"通货膨胀与货币政策调控", domain:"经济学", difficulty:"中", diffClass:"is-moderate",
    summary:"通货膨胀是物价水平的持续普遍上涨，中央银行通过利率、准备金率、公开市场操作等工具调控货币供应量，以维持物价稳定。",
    quickQs:["通货膨胀的类型","货币政策三大工具","给我出道练习题","用通俗语言解释"],
    content:`<p>10年前100元能买一大篮菜，现在可能只够买半篮——这种"钱越来越不值钱"的现象就是<strong>通货膨胀</strong>。适度的通胀是经济健康的标志，但恶性通胀会摧毁经济。央行的重要职责就是"管住"通胀。</p>
<h3>什么是通货膨胀？</h3>
<p>通货膨胀不是某一种商品涨价（那是相对价格变化），而是<strong>整体物价水平的持续、普遍上涨</strong>。通常用CPI（消费者价格指数）来衡量：</p>
<div class="formula-block"><span class="formula-label">通货膨胀率</span>$$π = \\frac{CPI_t - CPI_{t-1}}{CPI_{t-1}} \\times 100\%$$</div>
<h3>通胀的三种类型</h3>
<table class="data-table">
<tr><th>类型</th><th>成因</th><th>典型特征</th></tr>
<tr><td>需求拉动型</td><td>总需求 &gt; 总供给</td><td>"太多货币追逐太少商品"</td></tr>
<tr><td>成本推动型</td><td>原材料/工资上涨</td><td>工资-物价螺旋上升</td></tr>
<tr><td>结构性通胀</td><td>经济结构失衡</td><td>部门间涨幅差异大</td></tr>
</table>
<h3>中央银行的"三把武器"</h3>
<p>央行通过调控货币供应量来抑制或刺激通胀：</p>
<ul style="padding-left:20px;">
<li><strong>公开市场操作</strong>：在二级市场买卖政府债券。买债券→向市场投放基础货币（宽松）；卖债券→收回货币（紧缩）。</li>
<li><strong>存款准备金率</strong>：规定商业银行必须留存多少存款不能贷出。提高→银行可贷资金减少→货币收缩。</li>
<li><strong>再贴现率</strong>：商业银行向央行借款的利率。提高→银行借钱成本上升→信贷收缩。</li>
</ul>
<p>抑制通胀的标准操作是<strong>紧缩性货币政策</strong>：加息、提高准备金率、卖出债券。反之，经济萧条时则用扩张性政策"放水"刺激。</p>`,
    quiz:[{ question:"中央银行在公开市场上卖出政府债券，主要目的是？", options:["A. 增加货币供应量（宽松）","B. 减少货币供应量（紧缩）","C. 降低利率","D. 刺激投资"], answerIndex:1 },
           { question:"需求拉动型通货膨胀的典型成因是？", options:["A. 生产成本上升","B. 总需求大于总供给","C. 技术进步","D. 货币升值"], answerIndex:1 }] }
);
