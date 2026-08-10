window.questionBank = window.questionBank || {};
window.questionBank.easy = window.questionBank.easy || [];
window.questionBank.easy.push(
  { id:15, title:"HTTP协议与Web通信基础", domain:"计算机", difficulty:"低", diffClass:"is-low",
    summary:"HTTP是浏览器和服务器之间的通信协议，基于请求-响应模式，通过方法和状态码实现标准化的数据交换。",
    quickQs:["GET和POST的区别","HTTP常见的状态码","给我出道练习题","用通俗语言解释"],
    content:`<p>当你在浏览器地址栏输入网址并按下回车时，背后发生了什么？浏览器和服务器通过<strong>HTTP协议</strong>（超文本传输协议）进行对话。HTTP定义了一套标准化的"语言"，让全球任意浏览器都能和任意Web服务器正确交流。</p>
<h3>请求-响应模型</h3>
<p>HTTP采用简单的对话模式：<strong>客户端发请求 → 服务器回响应</strong>。就像你去餐厅点餐（请求），厨房做好端上来（响应）。每次对话都是独立的——HTTP本身不会记住你是谁（这叫做"无状态"），网站通过Cookie/Session机制来弥补这一点。</p>
<h3>常用的HTTP方法</h3>
<table class="data-table">
<tr><th>方法</th><th>用途</th><th>类比</th></tr>
<tr><td>GET</td><td>从服务器获取资源</td><td>去图书馆借书（只看不改）</td></tr>
<tr><td>POST</td><td>向服务器提交数据</td><td>填写表单提交（新增数据）</td></tr>
<tr><td>PUT</td><td>更新服务器上的资源</td><td>修改已有的借阅记录</td></tr>
<tr><td>DELETE</td><td>删除服务器上的资源</td><td>归还并销毁记录</td></tr>
</table>
<h3>状态码：服务器告诉你的"结果"</h3>
<div class="formula-block"><span class="formula-label">常见状态码速查</span>
200 OK — 请求成功 ✅&nbsp;&nbsp;301 — 永久跳转到新地址<br>
302 — 临时跳转&nbsp;&nbsp;404 — 找不到资源（页面不存在）❌<br>
500 — 服务器内部错误 ☠️&nbsp;&nbsp;403 — 无权限访问 🔒</div>
<p>下次看到浏览器报错时，看一眼状态码就能知道大概出了什么问题：4开头一般是你的问题（地址错了或权限不够），5开头是服务器的问题（它自己挂了）。</p>`,
    quiz:[{ question:"用户在网页表单中输入信息并点击提交按钮，通常使用的HTTP方法是？", options:["A. GET","B. POST","C. PUT","D. DELETE"], answerIndex:1 },
           { question:"浏览器显示404 Not Found意味着什么？", options:["A. 服务器正在维护","B. 请求的资源不存在","C. 网络连接断了","D. 没有访问权限"], answerIndex:1 }] }
);
