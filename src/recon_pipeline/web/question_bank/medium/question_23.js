window.questionBank = window.questionBank || {};
window.questionBank.medium = window.questionBank.medium || [];
window.questionBank.medium.push(
  { id:23, title:"工作记忆模型与认知负荷", domain:"心理学", difficulty:"中", diffClass:"is-moderate",
    summary:"Baddeley工作记忆模型将记忆分为语音环路、视空模板和中央执行器，Sweller认知负荷理论区分内在、外在和相关负荷。",
    quickQs:["Baddeley模型的三个组件","三种认知负荷的区别","给我出道练习题","用通俗语言解释"],
    content:`<p>你正在读这句话时，能记住前面几个字吗？这个"此刻在脑海中保持并处理信息"的能力，叫做<strong>工作记忆</strong>。它是思考、学习和解决问题的核心舞台，也是教学设计和界面开发的理论基础。</p>
<h3>Baddeley工作记忆模型（1974）</h3>
<p>工作记忆不是一个简单的"暂存区"，而是一个多组件系统：</p>
<table class="data-table">
<tr><th>组件</th><th>功能</th><th>容量限制</th><th>典型现象</th></tr>
<tr><td>语音环路</td><td>处理言语/听觉信息</td><td>约2秒发音时长</td><td>读一长串数字容易忘</td></tr>
<tr><td>视空模板</td><td>处理视觉/空间信息</td><td>约3-4个物体</td><td>同时记多个位置困难</td></tr>
<tr><td>中央执行器</td><td>注意力控制、策略选择</td><td>有限且不可分割</td><td>一心二用容易出错</td></tr>
</table>
<p>2000年Baddeley又补充了<strong>情景缓冲器</strong>，负责整合语音、视空和长时记忆的信息。</p>
<h3>Sweller的认知负荷理论（1988）</h3>
<p>学习时工作记忆的负荷可分为三类：</p>
<div class="formula-block"><span class="formula-label">总负荷公式</span>总负荷 = 内在负荷 + 外在负荷 + 相关负荷<br>三者之和 ≤ 工作记忆总容量</div>
<ul style="padding-left:20px;">
<li><strong>内在负荷</strong>：内容本身的难度（如量子力学本身就难）</li>
<li><strong>外在负荷</strong>：不良教学设计造成的无用负担（如把图表和文字分开排版，迫使眼睛来回跳）</li>
<li><strong>相关负荷</strong>：构建"图式"（知识结构）的有效投入</li>
</ul>
<p>最优学习发生在：内在负荷适中、<strong>外在负荷最小化</strong>（删掉无用的花哨设计）、剩余容量全部用于相关负荷的状态。这也是为什么好的教材和课件都强调"图文一体、避免分心"。</p>`,
    quiz:[{ question:"把图表和配套文字分页放置，会增加哪种认知负荷？", options:["A. 内在负荷","B. 外在负荷","C. 相关负荷","D. 总记忆容量"], answerIndex:1 },
           { question:"Baddeley工作记忆模型中负责注意力控制和策略选择的核心组件是？", options:["A. 语音环路","B. 视空模板","C. 中央执行器","D. 情景缓冲器"], answerIndex:2 }] }
);
